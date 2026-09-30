"""회사 계정 ↔ 스코핑 템플릿 링크 (8-C, ADR-0037 §4).

템플릿은 실제 원천(`seeds/` 스코핑 엑셀, ICFR_STD v1)을 적재해 쓴다 — 계정명 규칙이 실제 템플릿과
맞는지가 검증 대상이기 때문이다. 회사 계정은 8-B2 결합 결과와 같은 모양(공시 행 아래 COA 잎)으로 만든다.
테스트마다 새 테넌트(계정 마스터가 테넌트 단위).
"""
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.core.tenant_context import reset_active_tenant, set_active_tenant
from app.models.financial_statement import FsTemplateLink
from app.services import financial_statement as svc
from app.services.fs_template_match import judge, normalized_key
from seeds.seed_scoping_template import load_template
from tests.conftest import TestingSessionLocal
from tests.test_fs_upload import _tenant


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


def _master(tid) -> dict[str, str]:
    """공시 행 아래 COA 잎 — 8-B2 결합 결과와 같은 모양. {이름: id}."""
    db = TestingSessionLocal()
    tok = set_active_tenant(tid)
    try:
        c = svc.create_account
        ar = c(db, statement_type="BS", name="매출채권및기타채권", section="asset", is_subtotal=True)
        ppe = c(db, statement_type="BS", name="유형자산", section="asset", is_subtotal=True)
        rou = c(db, statement_type="BS", name="사용권자산", section="asset", is_subtotal=True)
        inv = c(db, statement_type="BS", name="투자부동산", section="asset", is_subtotal=True)
        cash = c(db, statement_type="BS", name="현금및현금성자산", section="asset", is_subtotal=True)
        acc = {"매출채권및기타채권": ar, "유형자산": ppe, "현금@공시": cash}
        # 공시 행과 같은 이름의 COA 잎(8-B2 결합 결과) — 잎에 제안한다
        acc["현금@잎"] = c(db, statement_type="BS", name="현금및현금성자산", section="asset", parent_id=cash.id)
        for name, parent in (("매출채권", ar), ("대손충당금", ar), ("미수금", ar), ("건물", ppe),
                             ("감가상각누계액_건물", ppe), ("사용권자산감가", rou)):
            acc[name] = c(db, statement_type="BS", name=name, section="asset", parent_id=parent.id)
        # 같은 이름이 서로 다른 공시 행 아래 반복 — 제안하지 않는다
        acc["감가상각누계액@사용권"] = c(db, statement_type="BS", name="감가상각누계액", section="asset",
                                        parent_id=rou.id)
        acc["감가상각누계액@투자"] = c(db, statement_type="BS", name="감가상각누계액", section="asset",
                                      parent_id=inv.id)
        db.commit()
        return {k: str(v.id) for k, v in acc.items()}
    finally:
        reset_active_tenant(tok)
        db.close()


def _matches(client, h, stype="BS") -> dict:
    r = client.get("/api/fs/template-matches", headers=h, params={"statement_type": stype})
    assert r.status_code == 200, r.text
    return r.json()


def _tmpl_id(m: dict, name: str) -> str:
    return next(t["id"] for t in m["template_accounts"] if t["name"] == name)


def _row(m: dict, account_id: str) -> dict:
    return next(r for r in m["accounts"] if r["account_id"] == account_id)


def _active_links(tid, account_id: str) -> int:
    db = TestingSessionLocal()
    tok = set_active_tenant(tid)
    try:
        return db.scalar(select(func.count()).select_from(FsTemplateLink).where(
            FsTemplateLink.account_id == UUID(account_id), FsTemplateLink.is_deleted == False))  # noqa: E712
    finally:
        reset_active_tenant(tok)
        db.close()


# ── 1. 이름 규칙 (순수) ───────────────────────────────────────

def test_name_rules() -> None:
    assert normalized_key("대손충당금(매출채권)") == "대손충당금"
    assert normalized_key("정부보조금_비품") == "정부보조금"
    assert normalized_key("2. 이자의 수취") == "이자의수취"
    assert normalized_key("(2) 비용가산 :") == "비용가산"
    assert judge("매출채권", "매출채권") == "exact"
    assert judge("이자의 수취", "2. 이자의 수취") == "normalized"
    assert judge("대손충당금", "대손충당금(매출채권)") == "normalized"
    assert judge("매출채권및기타채권", "매출채권") == "manual"


# ── 2. 제안 ───────────────────────────────────────────────────

def test_suggestions_are_not_saved(client: TestClient) -> None:
    h, tid = _tenant(client)
    acc = _master(tid)
    m = _matches(client, h)
    assert (m["template_code"], m["template_version"]) == ("ICFR_STD", 1)
    assert len(m["template_accounts"]) == 58                                        # 템플릿 BS 계정 수
    s = {k: (_row(m, v)["suggestion"] or {}) for k, v in acc.items()}
    assert (s["매출채권"]["template_name"], s["매출채권"]["basis"]) == ("매출채권", "exact")
    assert (s["대손충당금"]["template_name"], s["대손충당금"]["basis"]) == ("대손충당금(매출채권)", "normalized")
    assert s["감가상각누계액_건물"]["basis"] == "exact"
    assert s["감가상각누계액@사용권"] == {} and s["감가상각누계액@투자"] == {}        # 회사 쪽 반복 이름
    assert s["매출채권및기타채권"] == {}
    assert s["현금@잎"]["basis"] == "exact" and s["현금@공시"] == {}                  # 공시 행 ⊃ 같은 이름 잎
    assert _row(m, acc["매출채권및기타채권"])["depth"] == 0 and _row(m, acc["매출채권"])["depth"] == 1
    assert _row(m, acc["매출채권"])["parent_name"] == "매출채권및기타채권"
    order = [r["account_id"] for r in m["accounts"]]
    assert order.index(acc["매출채권및기타채권"]) < order.index(acc["매출채권"]) < order.index(acc["대손충당금"])
    assert all(r["link"] is None for r in m["accounts"])
    assert "linked" not in m["counts"] and m["counts"]["accounts"] == len(m["accounts"])
    assert _active_links(tid, acc["매출채권"]) == 0


# ── 3. 확정 ───────────────────────────────────────────────────

def test_confirm_basis_is_judged_by_server(client: TestClient) -> None:
    h, tid = _tenant(client)
    acc = _master(tid)
    m = _matches(client, h)
    ar_t, bad_t = _tmpl_id(m, "매출채권"), _tmpl_id(m, "대손충당금(매출채권)")
    r = client.post("/api/fs/template-links", headers=h, json={"links": [
        {"account_id": acc["매출채권"], "template_account_id": ar_t},
        {"account_id": acc["대손충당금"], "template_account_id": bad_t},
        {"account_id": acc["매출채권및기타채권"], "template_account_id": ar_t, "note": "공시 행 — 대표 계정"},
    ]})
    assert r.status_code == 200, r.text
    got = {x["account_id"]: x["basis"] for x in r.json()["links"]}
    assert got == {acc["매출채권"]: "exact", acc["대손충당금"]: "normalized", acc["매출채권및기타채권"]: "manual"}
    assert any("매출채권" in w and "2개" in w for w in r.json()["warnings"])           # 템플릿 1 ← 회사 2

    m2 = _matches(client, h)
    link = _row(m2, acc["대손충당금"])["link"]
    assert link["template_name"] == "대손충당금(매출채권)" and link["confirmed_by_id"]
    assert m2["counts"]["linked"] == 3
    assert next(t for t in m2["template_accounts"] if t["id"] == ar_t)["linked_count"] == 2


def test_relink_replaces_and_same_pair_is_idempotent(client: TestClient) -> None:
    h, tid = _tenant(client)
    acc = _master(tid)
    m = _matches(client, h)
    first = client.post("/api/fs/template-links", headers=h, json={"links": [
        {"account_id": acc["미수금"], "template_account_id": _tmpl_id(m, "미수금")}]}).json()["links"][0]
    same = client.post("/api/fs/template-links", headers=h, json={"links": [
        {"account_id": acc["미수금"], "template_account_id": _tmpl_id(m, "미수금")}]}).json()["links"][0]
    assert same["id"] == first["id"]
    other = client.post("/api/fs/template-links", headers=h, json={"links": [
        {"account_id": acc["미수금"], "template_account_id": _tmpl_id(m, "매출채권")}]})
    assert other.status_code == 200 and other.json()["links"][0]["basis"] == "manual"
    assert _active_links(tid, acc["미수금"]) == 1                                   # 회사 계정당 활성 1개


def test_confirm_rejects_bad_input(client: TestClient) -> None:
    h, tid = _tenant(client)
    acc = _master(tid)
    m = _matches(client, h)
    pl = _matches(client, h, "PL")
    ar_t = _tmpl_id(m, "매출채권")
    post = lambda links, **kw: client.post("/api/fs/template-links", headers=h, json={"links": links, **kw})  # noqa: E731
    r = post([{"account_id": acc["매출채권"], "template_account_id": pl["template_accounts"][0]["id"]}])
    assert r.status_code == 422 and "종류가 다릅니다" in r.json()["detail"]
    r = post([{"account_id": acc["매출채권"], "template_account_id": acc["건물"]}])        # 템플릿 계정 아님
    assert r.status_code == 422
    r = post([{"account_id": acc["매출채권"], "template_account_id": ar_t}] * 2)
    assert r.status_code == 422 and "두 번" in r.json()["detail"]
    r = post([{"account_id": "00000000-0000-0000-0000-000000000001", "template_account_id": ar_t}])
    assert r.status_code == 404
    assert post([{"account_id": acc["매출채권"], "template_account_id": ar_t}], template_version=99).status_code == 404
    assert post([]).status_code == 422
    assert _active_links(tid, acc["매출채권"]) == 0                                 # 실패는 아무것도 남기지 않는다


def test_unlink_and_permissions(client: TestClient) -> None:
    h, tid = _tenant(client)
    acc = _master(tid)
    m = _matches(client, h)
    lk = client.post("/api/fs/template-links", headers=h, json={"links": [
        {"account_id": acc["건물"], "template_account_id": _tmpl_id(m, "건물")}]}).json()["links"][0]

    viewer, _ = _tenant(client, roles=("external_auditor",))
    assert client.get("/api/fs/template-matches", headers=viewer, params={"statement_type": "BS"}).status_code == 200
    assert client.post("/api/fs/template-links", headers=viewer, json={"links": [
        {"account_id": acc["건물"], "template_account_id": _tmpl_id(m, "건물")}]}).status_code == 403
    assert client.delete(f"/api/fs/template-links/{lk['id']}", headers=viewer).status_code == 403

    # 다른 테넌트에서는 이 계정도 링크도 보이지 않는다
    other, _ = _tenant(client)
    assert client.post("/api/fs/template-links", headers=other, json={"links": [
        {"account_id": acc["건물"], "template_account_id": _tmpl_id(m, "건물")}]}).status_code == 404
    assert client.delete(f"/api/fs/template-links/{lk['id']}", headers=other).status_code == 404

    assert client.delete(f"/api/fs/template-links/{lk['id']}", headers=h).status_code == 204
    assert client.delete(f"/api/fs/template-links/{lk['id']}", headers=h).status_code == 404
    assert _row(_matches(client, h), acc["건물"])["link"] is None
    assert _active_links(tid, acc["건물"]) == 0


def test_matches_validation(client: TestClient) -> None:
    h, _ = _tenant(client)
    assert client.get("/api/fs/template-matches", headers=h, params={"statement_type": "NOTE"}).status_code == 422
    assert client.get("/api/fs/template-matches", headers=h,
                      params={"statement_type": "BS", "template_code": "없음"}).status_code == 404
