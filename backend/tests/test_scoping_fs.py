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
