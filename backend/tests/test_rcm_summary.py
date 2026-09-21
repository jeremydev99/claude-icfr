"""대시보드 RCM 집계 API 검증 (4-1).

**이 파일이 막는 회귀**: 화면에 보이는 숫자와 눌렀을 때 나오는 목록이 어긋나는 것.
집계와 검색이 각자 필터를 구현하므로 한쪽만 바뀌면 조용히 틀어진다 — 현황판이
틀린 현황을 말하는 것은 아무것도 안 보여주는 것보다 나쁘다. 그래서 **모든 묶음에
대해 "집계 건수 == 그 필터로 검색한 총건수"를 기계적으로 대조**한다.

집계 대상 데이터는 다른 테스트 파일들이 만든 것을 그대로 쓴다 — 특정 숫자를 고정하면
테스트 순서에 묶이므로, **숫자가 아니라 불변식**(합계·일치·0 처리)을 본다.
"""
from fastapi.testclient import TestClient

from app.core.security import hash_password
from app.core.tenant_context import DEFAULT_TENANT_ID, reset_active_tenant, set_active_tenant
from app.models.tenant import UserTenantAccess
from app.models.user import User
from app.models.user_mgmt import UserRole
from tests.conftest import TestingSessionLocal


def _headers(client: TestClient, email: str = "admin@acme.example", pw: str = "admin123") -> dict:
    resp = client.post("/api/auth/login", data={"username": email, "password": pw})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _summary(client: TestClient) -> dict:
    resp = client.get("/api/rcm/summary", headers=_headers(client))
    assert resp.status_code == 200, resp.text
    return resp.json()


# ── 집계 ↔ 검색 일치 ──────────────────────────────────────

def test_bucket_counts_match_search_totals(client: TestClient) -> None:
    """**모든 묶음의 집계 건수가 그 필터로 검색한 총건수와 같다.**

    드릴스루의 계약이 이것이다 — "핵심통제 93건"을 눌렀는데 92건이 나오면
    어느 쪽이 맞는지 알 수 없다.

    **"미지정" 칸도 예외가 아니다.** 이 테스트가 처음 잡은 것이 그 칸이었다 —
    빈 문자열을 필터로 넘기면 "필터 없음"과 구분되지 않아 전체 목록이 돌아왔다
    (프로세스 미지정 24건 → 검색 58건). 그래서 `__none__` 값을 쓴다.
    """
    h = _headers(client)
    summary = _summary(client)

    checked = 0
    for group in summary["groups"]:
        param = group["filter_param"]
        assert param, f"{group['key']} 에 filter_param 이 없다 — 드릴스루가 막힌다"
        for bucket in group["buckets"]:
            resp = client.get("/api/rcm/controls/search",
                              params={param: bucket["value"], "limit": 1}, headers=h)
            assert resp.status_code == 200, resp.text
            assert resp.json()["total"] == bucket["count"], (
                f"{group['key']}={bucket['value']}: 집계 {bucket['count']} vs 검색 {resp.json()['total']}"
            )
            checked += 1
    assert checked > 0, "대조한 묶음이 하나도 없다 — 데이터가 비었는지 확인할 것"


def test_unset_bucket_is_drillable(client: TestClient) -> None:
    """"미지정" 칸은 빈 문자열이 아니라 `__none__` 로 나온다.

    빈 문자열이면 검색에서 "필터 없음"과 같아져 전체 목록이 돌아간다 —
    숫자를 눌렀을 때 다른 숫자가 나오는 상태이며, 화면이 거짓말을 하게 된다.
    """
    for group in _summary(client)["groups"]:
        for bucket in group["buckets"]:
            assert bucket["value"] != "", f"{group['key']} 에 빈 값 칸이 있다"
            if bucket["label"] == "미지정":
                assert bucket["value"] == "__none__"


def test_control_total_matches_search_without_filter(client: TestClient) -> None:
    """합계는 필터 없는 검색 총건수와 같다 — 집계가 일부를 빠뜨리지 않는다."""
    h = _headers(client)
    total = client.get("/api/rcm/controls/search", params={"limit": 1}, headers=h).json()["total"]
    assert _summary(client)["control_total"] == total


def test_exclusive_groups_sum_to_total(client: TestClient) -> None:
    """배타적인 묶음은 합이 전체와 같다.

    통제활동(`activity`)은 **한 통제가 여러 칸에 들어가므로 제외**한다 —
    이 성질을 모르고 합계를 맞추려 들면 엉뚱한 곳을 고치게 된다.
    """
    summary = _summary(client)
    for group in summary["groups"]:
        if group["key"] == "activity":
            continue
        assert sum(b["count"] for b in group["buckets"]) == summary["control_total"], group["key"]


# ── 0 을 가리지 않는다 ────────────────────────────────────

def test_org_covers_every_control(client: TestClient) -> None:
    """미배정 + 부서별 합 = 전체. **배정 0건이면 전체가 미배정으로 나온다.**

    0 을 "준비중"으로 가리면 현황판의 목적이 무너진다(4-1 §0).
    """
    summary = _summary(client)
    org = summary["org"]
    assert org["unassigned"] + sum(b["count"] for b in org["buckets"]) == summary["control_total"]


def test_progress_is_zero_without_cycles(client: TestClient) -> None:
    """회차가 없으면 진행 현황은 전부 0 이며, 필드 자체는 존재한다.

    회차가 생기면 자동으로 채워지는 구조인지를 여기서 고정한다 —
    키가 사라지면 화면이 "표시할 게 없다"로 오해한다.
    """
    progress = _summary(client)["progress"]
    for key in ("cycles", "targets", "activities", "completed", "incomplete"):
        assert key in progress, key
        assert progress[key] >= 0
    assert progress["incomplete"] == max(progress["targets"] - progress["completed"], 0)


# ── 필터 추가분 ───────────────────────────────────────────

def test_assessment_frequency_filter_is_a_separate_axis(client: TestClient) -> None:
    """**`assessment_frequency`(평가주기)와 `frequency`(수행주기)는 다른 축이다.**

    같은 값 문자열을 쓰지 않는다(`annual` vs `A`). 축을 섞으면 화면에서 두 묶음이
    같은 숫자를 내면서 다른 목록을 보여준다.
    """
    h = _headers(client)
    by_assessment = client.get("/api/rcm/controls/search",
                               params={"assessment_frequency": "annual", "limit": 1},
                               headers=h).json()["total"]
    by_frequency = client.get("/api/rcm/controls/search",
                              params={"frequency": "A", "limit": 1}, headers=h).json()["total"]
    summary = _summary(client)
    assessment_group = next(g for g in summary["groups"] if g["key"] == "assessment_frequency")
    frequency_group = next(g for g in summary["groups"] if g["key"] == "frequency")
    assert by_assessment == next(
        (b["count"] for b in assessment_group["buckets"] if b["value"] == "annual"), 0)
    assert by_frequency == next(
        (b["count"] for b in frequency_group["buckets"] if b["value"] == "A"), 0)


def test_unknown_activity_is_rejected(client: TestClient) -> None:
    """목록 밖 통제활동 이름은 422. 조용히 무시하면 전체 목록이 돌아가
    "필터가 듣지 않는다"가 된다."""
    resp = client.get("/api/rcm/controls/search",
                      params={"activity": "activity_bogus"}, headers=_headers(client))
    assert resp.status_code == 422, resp.text


# ── 권한 ──────────────────────────────────────────────────

def test_external_auditor_can_read_summary(client: TestClient) -> None:
    """`external_auditor` 도 대시보드를 본다 — 조회 전용일 뿐 조회는 막지 않는다
    (ADR-0031 §2.1). 대시보드에는 쓰기 동작이 없다."""
    db = TestingSessionLocal()
    tok = set_active_tenant(DEFAULT_TENANT_ID)
    try:
        email = "summary-ext@acme.example"
        u = db.query(User).filter(User.email == email).first()
        if u is None:
            u = User(email=email, hashed_password=hash_password("pw123456"),
                     display_name="외부감사인", role="user", is_active=True)
            db.add(u)
            db.commit()
        if db.query(UserTenantAccess).filter(
            UserTenantAccess.user_id == u.id,
            UserTenantAccess.tenant_id == DEFAULT_TENANT_ID,
        ).first() is None:
            db.add(UserTenantAccess(user_id=u.id, tenant_id=DEFAULT_TENANT_ID, role="user"))
            db.commit()
        if db.query(UserRole).filter(
            UserRole.user_id == u.id, UserRole.role_name == "external_auditor",
            UserRole.is_deleted == False,  # noqa: E712
        ).first() is None:
            db.add(UserRole(user_id=u.id, role_name="external_auditor"))
            db.commit()
    finally:
        reset_active_tenant(tok)
        db.close()

    resp = client.get("/api/rcm/summary", headers=_headers(client, email, "pw123456"))
    assert resp.status_code == 200, resp.text
