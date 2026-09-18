"""부서·소속 API — 권한 가드와 재생성 가능성 (4-2).

**이 파일이 막는 회귀 두 가지.**

① **조직 구조의 쓰기가 `icfr_manager` 전용이라는 것.** 3-1 에서 `require_write` 로 둔 것은
   누락이었다 — 그러면 `external_auditor` 만 막히고 **일반 사용자가 부서를 만들 수 있다**
   (실측 201). 화면에서만 막으면 13.9-35 와 같은 상태가 된다.

② **지웠다가 다시 만들 수 있다는 것.** 유니크가 소프트 삭제 행까지 세면 같은 이름의 부서를
   다시 만들 수 없고, 소속도 뺐다가 다시 넣을 수 없다. 오타로 만든 부서를 지우고 다시 만드는
   것은 흔한 실무이며, 그때 돌아오던 문구는 "데이터 무결성 제약 위반" 이라 원인을 알 수 없었다.
"""
import pytest
from fastapi.testclient import TestClient

from app.core.security import hash_password
from app.core.tenant_context import DEFAULT_TENANT_ID, reset_active_tenant, set_active_tenant
from app.models.tenant import UserTenantAccess
from app.models.user import User
from app.models.user_mgmt import UserRole
from tests.conftest import TestingSessionLocal

PW = "pw123456"


def _account(email: str, name: str, roles: tuple[str, ...] = ()) -> str:
    """계정 + 테넌트 접근 + 테넌트 역할. 사전 상태만 직접 삽입한다."""
    db = TestingSessionLocal()
    tok = set_active_tenant(DEFAULT_TENANT_ID)
    try:
        u = db.query(User).filter(User.email == email).first()
        if u is None:
            u = User(email=email, hashed_password=hash_password(PW),
                     display_name=name, role="user", is_active=True)
            db.add(u)
            db.commit()
        if db.query(UserTenantAccess).filter(
            UserTenantAccess.user_id == u.id,
            UserTenantAccess.tenant_id == DEFAULT_TENANT_ID,
        ).first() is None:
            db.add(UserTenantAccess(user_id=u.id, tenant_id=DEFAULT_TENANT_ID, role="user"))
            db.commit()
        for r in roles:
            if db.query(UserRole).filter(
                UserRole.user_id == u.id, UserRole.role_name == r,
                UserRole.is_deleted == False,  # noqa: E712
            ).first() is None:
                db.add(UserRole(user_id=u.id, role_name=r))
        db.commit()
        return str(u.id)
    finally:
        reset_active_tenant(tok)
        db.close()


def _headers(client: TestClient, email: str) -> dict:
    resp = client.post("/api/auth/login", data={"username": email, "password": PW})
    assert resp.status_code == 200, resp.text
    return {"Authorization": "Bearer " + resp.json()["access_token"]}


@pytest.fixture()
def manager(client: TestClient) -> dict:
    _account("dept-mgr@acme.example", "부서관리자", ("icfr_manager",))
    return _headers(client, "dept-mgr@acme.example")


# ── ① 권한 ────────────────────────────────────────────────

def test_only_icfr_manager_can_create_department(client: TestClient, manager: dict) -> None:
    """일반 사용자는 부서를 만들 수 없다. **`can_write` 로 막으면 통과해 버린다** —
    일반 사용자는 `can_write=true` 다."""
    _account("dept-plain@acme.example", "일반사용자")
    plain = _headers(client, "dept-plain@acme.example")

    assert client.post("/api/org/departments", headers=plain,
                       json={"name": "무단부서"}).status_code == 403
    ok = client.post("/api/org/departments", headers=manager, json={"name": "권한확인팀"})
    assert ok.status_code == 201, ok.text
    client.delete(f"/api/org/departments/{ok.json()['id']}", headers=manager)


def test_external_auditor_cannot_write_but_can_read(client: TestClient, manager: dict) -> None:
    """`external_auditor` 는 조회 전용이다(ADR-0031 §2.1). **조회는 막지 않는다** —
    대시보드 조직별 집계와 화면이 부서를 읽어야 한다."""
    _account("dept-ext@acme.example", "외부감사인", ("external_auditor",))
    ext = _headers(client, "dept-ext@acme.example")

    assert client.post("/api/org/departments", headers=ext, json={"name": "감사부서"}).status_code == 403
    assert client.get("/api/org/departments", headers=ext).status_code == 200


def test_plain_user_can_read_departments(client: TestClient) -> None:
    """조회는 인증만 — 조직도를 보는 것 자체는 제한하지 않는다."""
    _account("dept-plain@acme.example", "일반사용자")
    assert client.get("/api/org/departments",
                      headers=_headers(client, "dept-plain@acme.example")).status_code == 200


# ── ② 지웠다가 다시 만들기 ────────────────────────────────

def test_department_name_is_reusable_after_delete(client: TestClient, manager: dict) -> None:
    """삭제한 부서의 이름을 다시 쓸 수 있다. 소프트 삭제 행이 이름을 계속 점유하면
    "오타로 만든 부서 지우고 다시 만들기"가 막힌다."""
    name = "재사용팀"
    first = client.post("/api/org/departments", headers=manager, json={"name": name})
    assert first.status_code == 201, first.text
    assert client.delete(f"/api/org/departments/{first.json()['id']}",
                         headers=manager).status_code == 204

    again = client.post("/api/org/departments", headers=manager, json={"name": name})
    assert again.status_code == 201, again.text
    client.delete(f"/api/org/departments/{again.json()['id']}", headers=manager)


def test_live_duplicate_name_gets_readable_message(client: TestClient, manager: dict) -> None:
    """살아 있는 이름 중복은 409 이며 **문구가 원인을 말한다.**
    DB 제약이 먼저 터지면 "데이터 무결성 제약 위반"이라 사용자가 알 수 없다."""
    first = client.post("/api/org/departments", headers=manager, json={"name": "중복확인팀"})
    dup = client.post("/api/org/departments", headers=manager, json={"name": "중복확인팀"})
    assert dup.status_code == 409
    assert "중복확인팀" in dup.json()["detail"]
    client.delete(f"/api/org/departments/{first.json()['id']}", headers=manager)


def test_membership_is_reusable_after_removal(client: TestClient, manager: dict) -> None:
    """소속을 뺐다가 다시 넣을 수 있다. **주 소속도 마찬가지다** — 소프트 삭제된 주 소속 행이
    남아 있으면 그 사람은 어느 부서에서도 다시 주 소속이 될 수 없었다(실측 409)."""
    uid = _account("dept-member@acme.example", "소속대상")
    dept = client.post("/api/org/departments", headers=manager, json={"name": "소속재사용팀"}).json()

    first = client.post("/api/org/memberships", headers=manager,
                        json={"user_id": uid, "department_id": dept["id"], "is_primary": True})
    assert first.status_code == 201, first.text
    assert client.delete(f"/api/org/memberships/{first.json()['id']}",
                         headers=manager).status_code == 204

    again = client.post("/api/org/memberships", headers=manager,
                        json={"user_id": uid, "department_id": dept["id"], "is_primary": True})
    assert again.status_code == 201, again.text

    client.delete(f"/api/org/memberships/{again.json()['id']}", headers=manager)
    client.delete(f"/api/org/departments/{dept['id']}", headers=manager)


# ── 삭제·주 소속·책임자 ───────────────────────────────────

def test_delete_is_blocked_while_members_remain(client: TestClient, manager: dict) -> None:
    """소속이 남아 있으면 409. 문구가 **무엇을 먼저 해야 하는지** 알려준다 —
    소속만 남으면 어느 부서인지 알 수 없다."""
    uid = _account("dept-member2@acme.example", "소속대상2")
    dept = client.post("/api/org/departments", headers=manager, json={"name": "삭제차단팀"}).json()
    m = client.post("/api/org/memberships", headers=manager,
                    json={"user_id": uid, "department_id": dept["id"], "is_primary": False}).json()

    blocked = client.delete(f"/api/org/departments/{dept['id']}", headers=manager)
    assert blocked.status_code == 409
    assert "소속" in blocked.json()["detail"]

    client.delete(f"/api/org/memberships/{m['id']}", headers=manager)
    assert client.delete(f"/api/org/departments/{dept['id']}", headers=manager).status_code == 204


def test_primary_membership_moves_instead_of_being_rejected(client: TestClient, manager: dict) -> None:
    """주 소속을 다른 부서로 지정하면 **거부가 아니라 이동**이다(부서 이동이 정상 업무다).
    화면도 이 동작에 맞춰 "기존 주 소속에서 옮겨집니다"를 안내한다."""
    uid = _account("dept-mover@acme.example", "이동대상")
    d1 = client.post("/api/org/departments", headers=manager, json={"name": "이동전팀"}).json()
    d2 = client.post("/api/org/departments", headers=manager, json={"name": "이동후팀"}).json()

    m1 = client.post("/api/org/memberships", headers=manager,
                     json={"user_id": uid, "department_id": d1["id"], "is_primary": True}).json()
    m2 = client.post("/api/org/memberships", headers=manager,
                     json={"user_id": uid, "department_id": d2["id"], "is_primary": True})
    assert m2.status_code == 201, m2.text

    rows = client.get("/api/org/memberships", headers=manager,
                      params={"user_id": uid}).json()["items"]
    primary = [r for r in rows if r["is_primary"]]
    assert len(primary) == 1, rows
    assert primary[0]["department_id"] == d2["id"]

    for mid in (m1["id"], m2.json()["id"]):
        client.delete(f"/api/org/memberships/{mid}", headers=manager)
    for d in (d1, d2):
        client.delete(f"/api/org/departments/{d['id']}", headers=manager)


def test_one_person_can_manage_several_departments(client: TestClient, manager: dict) -> None:
    """한 사람이 여러 부서의 책임자가 될 수 있고, **그 부서 소속이 아니어도 된다**
    (ADR-0031 §2.8 — 본부장이 팀장 퇴사 시 겸임하는 경우가 실재한다)."""
    boss = _account("dept-boss@acme.example", "본부장")
    d1 = client.post("/api/org/departments", headers=manager,
                     json={"name": "겸임팀1", "manager_id": boss})
    d2 = client.post("/api/org/departments", headers=manager,
                     json={"name": "겸임팀2", "manager_id": boss})
    assert d1.status_code == 201 and d2.status_code == 201
    assert d1.json()["manager_name"] == "본부장"

    members = client.get("/api/org/memberships", headers=manager,
                         params={"user_id": boss}).json()["items"]
    assert members == [], "책임자 지정이 소속을 만들지 않는다"

    for d in (d1, d2):
        client.delete(f"/api/org/departments/{d.json()['id']}", headers=manager)


# ── 대시보드 연결 (검증 9) ────────────────────────────────

def test_department_assignment_shows_up_in_dashboard_org_summary(
    client: TestClient, manager: dict,
) -> None:
    """**이 작업이 대시보드의 0 을 실제로 푸는지 본다.**

    부서 → 주 소속 → 통제책임자 배정까지 이어지면 조직별 집계에 그 부서가 나타나고
    미배정이 그만큼 줄어야 한다. 역할 배정 화면은 아직 없으므로 API 로 배정한다.
    """
    owner = _account("dept-owner@acme.example", "통제책임자")
    dept = client.post("/api/org/departments", headers=manager, json={"name": "집계연결팀"}).json()
    member = client.post("/api/org/memberships", headers=manager,
                         json={"user_id": owner, "department_id": dept["id"],
                               "is_primary": True}).json()

    before = client.get("/api/rcm/summary", headers=manager).json()["org"]

    controls = client.get("/api/rcm/controls/search", headers=manager,
                          params={"limit": 1}).json()["items"]
    if not controls:
        pytest.skip("통제가 없어 배정할 대상이 없다")
    assign = client.post("/api/org/assignments", headers=manager, json={
        "scope": "control", "target_id": controls[0]["id"],
        "role_name": "control_owner", "user_id": owner,
    })
    assert assign.status_code == 201, assign.text

    after = client.get("/api/rcm/summary", headers=manager).json()["org"]
    assert after["unassigned"] == before["unassigned"] - 1
    assert any(b["label"] == "집계연결팀" and b["count"] == 1 for b in after["buckets"]), after

    client.delete(f"/api/org/assignments/{assign.json()['id']}", headers=manager)
    client.delete(f"/api/org/memberships/{member['id']}", headers=manager)
    client.delete(f"/api/org/departments/{dept['id']}", headers=manager)
