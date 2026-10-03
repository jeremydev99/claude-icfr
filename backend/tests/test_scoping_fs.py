"""재무제표 기반 스코핑 생성 (8-E, ADR-0037 §6, 마스터 확정 A안 2026-09-30).

A안 — 기존 스코핑(2026, 템플릿 복사)은 그대로 두고 다음 회계연도부터 재무제표 기반으로 만든다.
테스트마다 새 테넌트. 템플릿은 실제 원천(ICFR_STD v1)을 적재해 쓴다(링크 기본값 검증).
"""
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from seeds.seed_scoping_template import load_template
from tests.conftest import TestingSessionLocal
from tests.test_fs_upload import PL_ROWS, _post, _tenant, _wb, bs_wb, horizontal_bs

D = Decimal


@pytest.fixture(scope="module", autouse=True)
def template(app):
    db = TestingSessionLocal()
    try:
        tpl, _, created = load_template(db)
        if created:
            db.commit()
        return tpl.id
    finally:
        db.close()


def _pl_wb(**kw):
    return _wb(("PL공시", "포 괄 손 익 계 산 서", PL_ROWS), **kw)


def _fs_2025(client, h, **kw) -> dict[tuple[str, int], str]:
    """공시 BS·PL 2025(확정)·2024(확정) — {(종류, 연도): statement_id}."""
    out = {}
    for wb in (bs_wb(**kw), _pl_wb(**kw)):
        r = _post(client, h, wb, mode="commit", include_prior="true")
        assert r.status_code == 200, r.text
        for s in r.json()["statements"]:
            out[(r.json()["statement_type"], s["fiscal_year"])] = s["statement_id"]
    for (t, y), sid in out.items():
        if y == 2024:
            assert client.post(f"/api/fs/statements/{sid}/finalize", headers=h, json={}).status_code == 200
    return out


def _create(client, h, fy=2026, source="financial_statements"):
    return client.post("/api/scoping", headers=h, json={"fiscal_year": fy, "source": source})


def _acc(detail: dict, name: str, stype: str) -> dict:
    return next(a for a in detail["accounts"] if a["name"] == name and a["statement_type"] == stype)


def test_requires_final_base_year_statements(client: TestClient) -> None:
    h, _ = _tenant(client)
    r = _create(client, h)
    assert r.status_code == 422 and "2025" in r.json()["detail"] and "BS" in r.json()["detail"]
    assert _post(client, h, bs_wb(), mode="commit").status_code == 200           # BS 만
    r = _create(client, h)
    assert r.status_code == 422 and "PL" in r.json()["detail"]
    assert client.get("/api/scoping", headers=h).json() == []                      # 실패는 아무것도 남기지 않는다


def test_rows_amounts_groups_and_fallbacks(client: TestClient) -> None:
    h, _ = _tenant(client)
    _fs_2025(client, h)
    r = _create(client, h)
    assert r.status_code == 201, r.text
    d = r.json()
    assert d["fiscal_year"] == 2026 and d["base_fiscal_year"] == 2025
    bs = [a for a in d["accounts"] if a["statement_type"] == "BS"]
    pl = [a for a in d["accounts"] if a["statement_type"] == "PL"]
    # 금액 트리의 잎만 — 소계·합계·섹션 머리·주당이익은 행이 아니다
    assert [a["name"] for a in bs] == ["현금및현금성자산", "매출채권", "유형자산", "매입채무", "자본금", "이익잉여금"]
    assert [a["name"] for a in pl] == ["영업수익", "영업비용", "금융수익", "금융비용", "법인세비용"]
    cash = _acc(d, "현금및현금성자산", "BS")
    assert (cash["current_amount"], cash["prior_amount"], cash["group_label"]) == (100, 100, "유동자산")
    assert _acc(d, "매출채권", "BS")["prior_amount"] == 150 and cash["fs_account_id"]
    # CF 확정본 없음 → 템플릿 CF 행, 주석은 템플릿 복사
    assert sum(1 for a in d["accounts"] if a["statement_type"] == "CF") == 51
    assert sum(1 for a in d["accounts"] if a["statement_type"] == "NOTE") == 38
    assert all(a["fs_account_id"] is None for a in d["accounts"] if a["statement_type"] in ("CF", "NOTE"))
    # 링크 없는 재무제표 계정은 질적 평가가 비어 있고 경고한다
    assert cash["ratings"] == {} and any("템플릿 연결이 없어" in w for w in d["warnings"])


def test_linked_accounts_get_template_defaults_with_badges(client: TestClient) -> None:
    h, _ = _tenant(client)
    _fs_2025(client, h)
    m = client.get("/api/fs/template-matches", headers=h, params={"statement_type": "BS"}).json()
    ar = next(r for r in m["accounts"] if r["name"] == "매출채권")
    assert ar["suggestion"]["basis"] == "exact"
    assert client.post("/api/fs/template-links", headers=h, json={"links": [
        {"account_id": ar["account_id"], "template_account_id": ar["suggestion"]["template_account_id"]}]}).status_code == 200
    d = _create(client, h).json()
    row = _acc(d, "매출채권", "BS")
    assert row["ratings"] and set(row["badges"]) >= {f"ratings.{k}" for k in row["ratings"]}
    assert all(v == "template" for v in row["badges"].values())
    assert _acc(d, "현금및현금성자산", "BS")["ratings"] == {}


def test_prior_amount_from_draft_comparative(client: TestClient) -> None:
    """전기(2024)가 비교 열로 들어와 작성 중이어도 전년 금액으로 쓴다(당기는 확정본만)."""
    h, _ = _tenant(client)
    for wb in (bs_wb(), _pl_wb()):
        assert _post(client, h, wb, mode="commit", include_prior="true").status_code == 200   # 2024 는 draft
    d = _create(client, h).json()
    assert _acc(d, "매출채권", "BS")["prior_amount"] == 150


def test_unit_conversion_to_won(client: TestClient) -> None:
    h, _ = _tenant(client)
    _fs_2025(client, h, unit="(단위 : 백만원)")
    d = _create(client, h).json()
    assert _acc(d, "유형자산", "BS")["current_amount"] == 500_000_000
    assert _acc(d, "영업비용", "PL")["current_amount"] == 600_000_000


def test_suspense_rows_are_not_scoping_accounts(client: TestClient) -> None:
    h, _ = _tenant(client)
    r = _post(client, h, horizontal_bs(stale_parent=True), mode="commit", unit=1, fiscal_years="2025,2024")
    sid = next(s["statement_id"] for s in r.json()["statements"] if s["fiscal_year"] == 2025)
    for x in client.get(f"/api/fs/statements/{sid}/suspense", headers=h).json():
        assert client.post(f"/api/fs/statements/{sid}/suspense/{x['amount_id']}/resolve", headers=h,
                           json={"action": "accept", "reason": "유지"}).status_code == 200
    assert client.post(f"/api/fs/statements/{sid}/finalize", headers=h, json={}).status_code == 200
    assert _post(client, h, _pl_wb(), mode="commit").status_code == 200
    d = _create(client, h)
    assert d.status_code == 201, d.text
    names = [a["name"] for a in d.json()["accounts"] if a["statement_type"] == "BS"]
    assert "임시계정(원본 차이)" not in names and "현금" in names and "자기주식" in names


def test_template_source_unchanged_and_bad_source(client: TestClient) -> None:
    h, _ = _tenant(client)
    d = _create(client, h, source="template").json()
    assert len(d["accounts"]) == 192 and all(a["fs_account_id"] is None for a in d["accounts"])
    assert _create(client, h, fy=2027, source="excel").status_code == 422
    viewer, _ = _tenant(client, roles=("external_auditor",))
    assert _create(client, viewer, fy=2028).status_code == 403


# ── 중요성 기준값·다시 불러오기 (2026-10-03) ───────────────────────

def _bench(d: dict) -> dict:
    return {b["kind"]: b["base_amount"] for b in d["benchmarks"]}


def test_fs_based_create_fills_benchmark_base_amounts(client: TestClient) -> None:
    """세전이익·매출액·총자산·총자본은 이름으로 찾고, 총비용 = 영업비용+금융비용+기타영업외비용+법인세비용."""
    h, _ = _tenant(client)
    _fs_2025(client, h)
    d = _create(client, h).json()
    b = _bench(d)
    assert b["adjusted_pbt"] == 430 and b["revenue"] == 1000
    assert b["total_expenses"] == 600 + 20 + 30      # 기타영업외비용 없음 → 있는 것만
    assert b["total_assets"] is not None and b["total_equity"] is not None
    assert b["operating_cf"] is None                  # CF 확정본 없음 → 비움(추정하지 않는다)
    assert d["overall_materiality"] is not None       # 기준값이 생겨 중요성이 계산된다


def test_reload_from_fs_replaces_template_rows(client: TestClient) -> None:
    """재무제표를 스코핑보다 나중에 올린 경우 — 템플릿으로 만든 작성 중 스코핑을 재무제표로 다시 채운다."""
    h, _ = _tenant(client)
    d = _create(client, h, source="template").json()
    assert all(a["fs_account_id"] is None for a in d["accounts"]) and _bench(d)["revenue"] is None
    _fs_2025(client, h)
    r = client.post(f"/api/scoping/{d['id']}/reload-from-fs", headers=h)
    assert r.status_code == 200, r.text
    d2 = r.json()
    assert _acc(d2, "현금및현금성자산", "BS")["current_amount"] == 100
    assert _bench(d2)["revenue"] == 1000 and d2["id"] == d["id"]
    ev = client.get(f"/api/scoping/{d['id']}/events", headers=h).json()
    reload_ev = [e for e in ev if e["target"] == "재무제표에서 다시 불러오기"]
    assert len(reload_ev) == 1 and reload_ev[0]["after"]["새 계정 행"] > 0
    # 대량 교체는 행마다 이력을 남기지 않는다(요약 1건)
    assert not any(e["action"] == "value_change" and (e["target"] or "").startswith("계정 ") for e in ev)
    # 검토 요청 후에는 다시 불러올 수 없다
    client.patch(f"/api/scoping/{d['id']}", headers=h, json={"rationale": "근거"})
    assert client.post(f"/api/scoping/{d['id']}/transition", headers=h, json={"to_status": "review"}).status_code == 200
    assert client.post(f"/api/scoping/{d['id']}/reload-from-fs", headers=h).status_code == 409


# ── 해당 없음 (2026-10-03) ─────────────────────────────────

def test_not_applicable_excludes_from_judgement_and_badges(client: TestClient) -> None:
    h, _ = _tenant(client)
    _fs_2025(client, h)
    d = _create(client, h).json()
    base = f"/api/scoping/{d['id']}"
    note = next(a for a in d["accounts"] if a["statement_type"] == "NOTE" and a["badges"])
    before = d["badge_count"]
    # 사유 없이 지정 불가
    assert client.patch(f"{base}/accounts/{note['id']}", headers=h, json={"not_applicable": True}).status_code == 422
    d2 = client.patch(f"{base}/accounts/{note['id']}", headers=h,
                      json={"not_applicable": True, "na_reason": "해당 거래 없음"}).json()
    row = next(a for a in d2["accounts"] if a["id"] == note["id"])
    assert row["not_applicable"] and row["final"] == "na" and row["quant"] == "na" and row["na_reason"] == "해당 거래 없음"
    assert d2["badge_count"] == before - len(note["badges"])   # 그 줄의 템플릿 값은 세지 않는다
    # 일괄 해제
    d3 = client.post(f"{base}/accounts/not-applicable", headers=h,
                     json={"account_ids": [note["id"]], "value": False}).json()
    assert next(a for a in d3["accounts"] if a["id"] == note["id"])["not_applicable"] is False
    assert d3["badge_count"] == before
    # 일괄 지정은 사유 필수, 요약에 na 집계
    assert client.post(f"{base}/accounts/not-applicable", headers=h,
                       json={"account_ids": [note["id"]], "value": True}).status_code == 422
    client.post(f"{base}/accounts/not-applicable", headers=h,
                json={"account_ids": [note["id"]], "value": True, "reason": "금액 0"})
    assert client.get("/api/scoping/summary", headers=h).json()["by_statement"]["NOTE"]["na"] == 1
