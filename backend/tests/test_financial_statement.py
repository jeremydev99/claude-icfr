"""재무제표·계정 트리 검증 (8-A, ADR-0037).

데이터는 서비스 함수로 넣는다 — 8-A 에는 계정·금액 쓰기 API 가 없다(마스터 확정 Q5).
**확정·재오픈·조회는 HTTP 로 부른다**(13.9-35 교훈 — 검증 대상 동작은 실제 경로로).

계정 마스터는 테넌트 하나를 테스트들이 공유하므로, 각 테스트는 자기 계정 id 로만 판정하고
재무제표는 서로 다른 회계연도를 쓴다.
"""
from contextlib import contextmanager
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.security import hash_password
from app.core.tenant_context import DEFAULT_TENANT_ID, reset_active_tenant, set_active_tenant
from app.models.financial_statement import FsAccount, FsStatement, FsStatementStatusEvent
from app.models.tenant import Tenant, UserTenantAccess
from app.models.user import User
from app.models.user_mgmt import UserRole
from app.services import financial_statement as svc
from tests.conftest import TestingSessionLocal

PW = "pw123456"
D = Decimal


# ── 준비 ───────────────────────────────────────────────────

@contextmanager
def session(tenant_id=DEFAULT_TENANT_ID):
    db = TestingSessionLocal()
    tok = set_active_tenant(tenant_id)
    try:
        yield db
    finally:
        reset_active_tenant(tok)
        db.close()


def _account(email: str, roles: tuple[str, ...] = ()) -> None:
    with session() as db:
        u = db.query(User).filter(User.email == email).first()
        if u is None:
            u = User(email=email, hashed_password=hash_password(PW), display_name=email.split("@")[0],
                     role="user", is_active=True)
            db.add(u)
            db.commit()
        if db.query(UserTenantAccess).filter(UserTenantAccess.user_id == u.id,
                                             UserTenantAccess.tenant_id == DEFAULT_TENANT_ID).first() is None:
            db.add(UserTenantAccess(user_id=u.id, tenant_id=DEFAULT_TENANT_ID, role="user"))
            db.commit()
        for r in roles:
            if db.query(UserRole).filter(UserRole.user_id == u.id, UserRole.role_name == r,
                                         UserRole.is_deleted == False).first() is None:  # noqa: E712
                db.add(UserRole(user_id=u.id, role_name=r))
        db.commit()


def _headers(client: TestClient, email: str) -> dict:
    r = client.post("/api/auth/login", data={"username": email, "password": PW})
    assert r.status_code == 200, r.text
    return {"Authorization": "Bearer " + r.json()["access_token"]}


def _user_id(email: str):
    with session() as db:
        return db.query(User).filter(User.email == email).first().id


@pytest.fixture()
def mgr(client: TestClient) -> dict:
    _account("fs-mgr@acme.example", ("icfr_manager",))
    return _headers(client, "fs-mgr@acme.example")


@pytest.fixture()
def viewer(client: TestClient) -> dict:
    _account("fs-viewer@acme.example", ("external_auditor",))
    return _headers(client, "fs-viewer@acme.example")


def _bs_accounts(db) -> dict[str, FsAccount]:
    """자산총계 ─ 유동자산 ─ {현금, 매출채권} / 부채총계 ─ 매입채무 / 자본총계 ─ 자본금.

    키는 테스트 안에서만 쓰는 이름이다 — 서비스는 계정명을 보지 않는다.
    """
    tag = uuid4().hex[:6]
    c = svc.create_account
    acc = {}
    acc["A"] = c(db, statement_type="BS", name=f"자산총계{tag}", section="asset", is_subtotal=True)
    acc["CA"] = c(db, statement_type="BS", name=f"유동자산{tag}", section="asset", is_subtotal=True,
                  parent_id=acc["A"].id, sort_order=1)
    acc["cash"] = c(db, statement_type="BS", name=f"현금{tag}", section="asset", parent_id=acc["CA"].id,
                    sort_order=1)
    acc["ar"] = c(db, statement_type="BS", name=f"매출채권{tag}", section="asset", parent_id=acc["CA"].id,
                  sort_order=2)
    acc["L"] = c(db, statement_type="BS", name=f"부채총계{tag}", section="liability", is_subtotal=True)
    acc["ap"] = c(db, statement_type="BS", name=f"매입채무{tag}", section="liability", parent_id=acc["L"].id)
    acc["E"] = c(db, statement_type="BS", name=f"자본총계{tag}", section="equity", is_subtotal=True)
    acc["cs"] = c(db, statement_type="BS", name=f"자본금{tag}", section="equity", parent_id=acc["E"].id)
    return acc


BALANCED = {"A": 300, "CA": 300, "cash": 100, "ar": 200, "L": 120, "ap": 120, "E": 180, "cs": 180}


def _bs(db, year: int, values: dict | None = None, *, unit: int = 1, basis: str = "separate",
        tolerance=0, acc: dict | None = None):
    acc = acc or _bs_accounts(db)
    st = svc.create_statement(db, fiscal_year=year, statement_type="BS", basis=basis, unit=unit,
                              tolerance=tolerance)
    for k, v in (values or BALANCED).items():
        svc.set_amount(db, st, acc[k], v)
    db.commit()
    return st, acc


def _rules(result: dict) -> list[str]:
    return [e["rule"] for e in result["errors"]]


# ── 1. 3단 이상 트리 저장·조회 (재귀 CTE) ──────────────────

def test_tree_four_levels_via_recursive_cte(client: TestClient, viewer: dict) -> None:
    with session() as db:
        acc = _bs_accounts(db)
        leaf = svc.create_account(db, statement_type="BS", name="보통예금", section="asset",
                                  parent_id=acc["cash"].id)
        db.commit()
        root_id, leaf_id = acc["A"].id, leaf.id
        depths = {a.id: d for a, d in svc.account_tree_rows(db, "BS")}
        assert depths[root_id] == 0 and depths[acc["CA"].id] == 1
        assert depths[acc["cash"].id] == 2 and depths[leaf_id] == 3

    r = client.get("/api/fs/accounts", params={"statement_type": "BS"}, headers=viewer)
    assert r.status_code == 200, r.text
    root = next(n for n in r.json() if n["id"] == str(root_id))
    ca = root["children"][0]
    assert [c["depth"] for c in (root, ca, ca["children"][0], ca["children"][0]["children"][0])] == [0, 1, 2, 3]
    assert ca["children"][0]["children"][0]["id"] == str(leaf_id)
    # 형제는 sort_order 순
    assert [c["sort_order"] for c in ca["children"]] == [1, 2]


# ── 2. 순환 거부 ───────────────────────────────────────────

def test_cycle_rejected_self_and_descendant(app) -> None:
    with session() as db:
        acc = _bs_accounts(db)
        db.commit()
        with pytest.raises(svc.FsError, match="자기 자신"):
            svc.set_parent(db, acc["A"], acc["A"].id)
        with pytest.raises(svc.FsError, match="자손"):
            svc.set_parent(db, acc["A"], acc["CA"].id)       # 자식
        with pytest.raises(svc.FsError, match="자손"):
            svc.set_parent(db, acc["A"], acc["cash"].id)     # 손자
        db.rollback()
        # 서비스를 우회해도 자기 참조는 DB CHECK 가 막는다
        root = svc.get_account(db, acc["A"].id)
        root.parent_id = root.id
        with pytest.raises(IntegrityError):
            db.flush()
        db.rollback()


def test_parent_must_share_statement_type_and_bs_section(app) -> None:
    with session() as db:
        acc = _bs_accounts(db)
        rev = svc.create_account(db, statement_type="PL", name="매출", section="revenue")
        with pytest.raises(svc.FsError, match="종류"):
            svc.set_parent(db, rev, acc["A"].id)
        with pytest.raises(svc.FsError, match="섹션"):
            svc.set_parent(db, acc["ap"], acc["A"].id)       # 부채를 자산 아래에
        with pytest.raises(svc.FsError):
            svc.create_account(db, statement_type="BS", name="x", section="revenue")
        db.rollback()


# ── 3. 자산 = 부채 + 자본 ──────────────────────────────────

def test_balance_pass_and_fail_with_diff(app) -> None:
    with session() as db:
        ok, acc = _bs(db, 2101)
        assert svc.validate(db, ok)["ok"] is True
        bad, _ = _bs(db, 2102, {**BALANCED, "L": 130, "ap": 130})
        r = svc.validate(db, bad)
        assert r["ok"] is False
        bal = next(e for e in r["errors"] if e["rule"] == svc.RULE_BALANCE)
        assert (bal["actual"], bal["expected"], bal["diff"]) == (D(300), D(310), D(-10))


# ── 4. 소계 = 하위합 ───────────────────────────────────────

def test_subtotal_pass_and_fail_names_account_and_diff(app) -> None:
    with session() as db:
        st, acc = _bs(db, 2103, {**BALANCED, "cash": 105})
        r = svc.validate(db, st)
        assert _rules(r) == [svc.RULE_SUBTOTAL]
        e = r["errors"][0]
        assert e["account_id"] == acc["CA"].id
        assert (e["expected"], e["actual"], e["diff"]) == (D(305), D(300), D(-5))


def test_pl_rollup_sign_subtracts_expense(app) -> None:
    """매출총이익 = 매출 − 매출원가. 비용은 양수로 표시하고 rollup_sign -1 로 뺀다(Q2)."""
    with session() as db:
        gp = svc.create_account(db, statement_type="PL", name="매출총이익", section="profit", is_subtotal=True)
        rev = svc.create_account(db, statement_type="PL", name="매출액", section="revenue", parent_id=gp.id)
        cogs = svc.create_account(db, statement_type="PL", name="매출원가", section="expense",
                                  parent_id=gp.id, rollup_sign=-1)
        st = svc.create_statement(db, fiscal_year=2104, statement_type="PL", basis="separate")
        for a, v in ((gp, 400), (rev, 1000), (cogs, 600)):
            svc.set_amount(db, st, a, v)
        assert svc.validate(db, st)["ok"] is True
        svc.set_amount(db, st, gp, 1600)   # 부호를 무시하고 더한 값이면 실패해야 한다
        assert _rules(svc.validate(db, st)) == [svc.RULE_SUBTOTAL]
        db.rollback()


def test_heading_without_row_rolls_up_grandchildren(app) -> None:
    """금액 행이 없는 중간 계정(제목)도 윗 소계가 그 아래 금액을 빠뜨리지 않는다."""
    with session() as db:
        values = {k: v for k, v in BALANCED.items() if k != "CA"}
        st, _ = _bs(db, 2105, values)
        assert svc.validate(db, st)["ok"] is True


# ── 5·Q6. 확정 관문 ────────────────────────────────────────

def test_finalize_rejected_when_validation_fails(client: TestClient, mgr: dict) -> None:
    with session() as db:
        st, acc = _bs(db, 2106, {**BALANCED, "cash": 105})
        sid, ca_id = st.id, acc["CA"].id
    r = client.post(f"/api/fs/statements/{sid}/finalize", headers=mgr, json={})
    assert r.status_code == 422, r.text
    errs = r.json()["detail"]["validation"]["errors"]
    assert errs[0]["rule"] == "subtotal" and errs[0]["account_id"] == str(ca_id)
    assert D(errs[0]["diff"]) == D(-5)
    d = client.get(f"/api/fs/statements/{sid}", headers=mgr).json()
    assert d["status"] == "draft" and d["events"] == []


def test_q6a_subtotal_without_children_blocks_finalize(client: TestClient, mgr: dict) -> None:
    with session() as db:
        acc = _bs_accounts(db)
        lonely = svc.create_account(db, statement_type="BS", name="기타자산", section="asset",
                                    is_subtotal=True, parent_id=acc["A"].id, sort_order=9)
        st, _ = _bs(db, 2107, {**BALANCED}, acc=acc)
        svc.set_amount(db, st, lonely, 0)
        db.commit()
        sid, lonely_id = st.id, lonely.id
        r = svc.validate(db, st)
        assert [(e["rule"], e["account_id"]) for e in r["errors"]] == [(svc.RULE_SUBTOTAL_NO_CHILDREN, lonely_id)]
    assert client.post(f"/api/fs/statements/{sid}/finalize", headers=mgr, json={}).status_code == 422


def test_q6b_subtotal_amount_missing_is_skipped_not_blocking(client: TestClient, mgr: dict) -> None:
    with session() as db:
        st, acc = _bs(db, 2108, {**BALANCED, "CA": None})
        sid, ca_id = st.id, acc["CA"].id
    v = client.get(f"/api/fs/statements/{sid}/validation", headers=mgr).json()
    assert v["ok"] is True and v["errors"] == []
    assert [(s["rule"], s["account_id"]) for s in v["skipped"]] == [("subtotal_amount_missing", str(ca_id))]
    r = client.post(f"/api/fs/statements/{sid}/finalize", headers=mgr, json={"reason": "결산 확정"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "final"
    assert len(body["validation"]["skipped"]) == 1          # 응답에 별도 항목
    ev = body["events"][0]
    assert (ev["to_status"], ev["skipped_count"], D(ev["tolerance"])) == ("final", 1, D(0))
    assert ev["tolerance_diffs"] is None                    # 허용 오차 0 이면 차액을 남기지 않는다


# ── Q3. 허용 오차 경계 ─────────────────────────────────────

def test_tolerance_boundary_and_recorded_on_finalize(client: TestClient, mgr: dict) -> None:
    with session() as db:
        at_edge, acc = _bs(db, 2109, {**BALANCED, "cash": 101}, tolerance=1)      # diff = tolerance
        over, _ = _bs(db, 2110, {**BALANCED, "cash": 102}, tolerance=1)           # diff = tolerance + 1
        assert svc.validate(db, at_edge)["ok"] is True
        r = svc.validate(db, over)
        assert r["ok"] is False and r["errors"][0]["diff"] == D(-2)
        sid, ca_id = at_edge.id, acc["CA"].id
    r = client.post(f"/api/fs/statements/{sid}/finalize", headers=mgr, json={})
    assert r.status_code == 200, r.text
    ev = r.json()["events"][-1]
    assert D(ev["tolerance"]) == D(1)
    diffs = {(x["rule"], x["account_id"]): D(x["diff"]) for x in ev["tolerance_diffs"]}
    assert diffs[("subtotal", str(ca_id))] == D(-1)
    assert diffs[("balance", None)] == D(0)                  # 규칙별 실제 차액을 전부 남긴다


# ── Q4. 재오픈 ─────────────────────────────────────────────

def test_reopen_twice_keeps_history(client: TestClient, mgr: dict, viewer: dict) -> None:
    with session() as db:
        st, _ = _bs(db, 2111)
        sid = st.id
    url = f"/api/fs/statements/{sid}"
    assert client.post(f"{url}/reopen", headers=mgr, json={"reason": "x"}).status_code == 409   # draft
    for i in range(2):
        assert client.post(f"{url}/finalize", headers=mgr, json={}).status_code == 200
        assert client.post(f"{url}/reopen", headers=mgr, json={"reason": "  "}).status_code == 422
        r = client.post(f"{url}/reopen", headers=mgr, json={"reason": f"수정 {i + 1}"})
        assert r.status_code == 200, r.text
    evs = client.get(url, headers=viewer).json()["events"]
    assert [(e["from_status"], e["to_status"]) for e in evs] == [("draft", "final"), ("final", "draft")] * 2
    assert [e["reason"] for e in evs if e["to_status"] == "draft"] == ["수정 1", "수정 2"]
    d = client.get(url, headers=viewer).json()
    assert d["status"] == "draft" and d["finalized_at"] is None


def test_finalize_and_reopen_require_icfr_manager(client: TestClient, viewer: dict) -> None:
    with session() as db:
        st, _ = _bs(db, 2112)
        sid = st.id
    assert client.get(f"/api/fs/statements/{sid}", headers=viewer).status_code == 200
    assert client.post(f"/api/fs/statements/{sid}/finalize", headers=viewer, json={}).status_code == 403


def test_final_statement_rejects_amount_writes(client: TestClient, mgr: dict) -> None:
    with session() as db:
        st, acc = _bs(db, 2113)
        sid, cash_id = st.id, acc["cash"].id
    assert client.post(f"/api/fs/statements/{sid}/finalize", headers=mgr, json={}).status_code == 200
    with session() as db:
        st = svc.get_statement(db, sid)
        with pytest.raises(svc.FsConflictError):
            svc.set_amount(db, st, svc.get_account(db, cash_id), 1)


def test_amount_scale_is_not_silently_rounded(app) -> None:
    with session() as db:
        acc = _bs_accounts(db)
        st = svc.create_statement(db, fiscal_year=2114, statement_type="BS", basis="separate")
        svc.set_amount(db, st, acc["cash"], D("10.25"))
        with pytest.raises(svc.FsError, match="소수"):
            svc.set_amount(db, st, acc["cash"], D("10.255"))
        db.rollback()


# ── 6. 단위 ────────────────────────────────────────────────

def test_units_validated_in_own_unit(client: TestClient, viewer: dict) -> None:
    """천원·백만원 재무제표를 각각 저장 — 검증·차액은 각자 단위 그대로다(원으로 환산하지 않는다)."""
    with session() as db:
        acc = _bs_accounts(db)
        k, _ = _bs(db, 2115, BALANCED, unit=1000, acc=acc)
        m, _ = _bs(db, 2115, {**BALANCED, "cash": 101}, unit=1000000, acc=acc, basis="consolidated")
        kid, mid = k.id, m.id
        with pytest.raises(svc.FsError, match="단위"):
            svc.create_statement(db, fiscal_year=2116, statement_type="BS", basis="separate", unit=10)
    vk = client.get(f"/api/fs/statements/{kid}/validation", headers=viewer).json()
    vm = client.get(f"/api/fs/statements/{mid}/validation", headers=viewer).json()
    assert (vk["unit"], vk["ok"]) == (1000, True)
    assert (vm["unit"], vm["ok"]) == (1000000, False)
    assert D(vm["errors"][0]["diff"]) == D(-1)               # 1 백만원, 1,000,000 이 아니다


# ── 7. 연결·별도 공존 ──────────────────────────────────────

def test_consolidated_and_separate_coexist_same_year(client: TestClient, viewer: dict) -> None:
    with session() as db:
        acc = _bs_accounts(db)
        _bs(db, 2117, acc=acc, basis="separate")
        _bs(db, 2117, acc=acc, basis="consolidated")
        with pytest.raises(IntegrityError):
            svc.create_statement(db, fiscal_year=2117, statement_type="BS", basis="separate")
        db.rollback()
    r = client.get("/api/fs/statements", params={"fiscal_year": 2117}, headers=viewer)
    assert sorted(s["basis"] for s in r.json()) == ["consolidated", "separate"]


# ── 8. 계정 폐지 후 과거 금액 ──────────────────────────────

def test_retired_account_keeps_past_amounts(client: TestClient, viewer: dict) -> None:
    with session() as db:
        st, acc = _bs(db, 2118)
        svc.retire_account(db, acc["ar"], 2118)
        db.commit()
        sid, ar_id = st.id, acc["ar"].id
        nxt = svc.create_statement(db, fiscal_year=2119, statement_type="BS", basis="separate")
        with pytest.raises(svc.FsError, match="유효하지"):
            svc.set_amount(db, nxt, acc["ar"], 1)
        db.rollback()
        assert db.scalars(select(FsAccount).where(FsAccount.id == ar_id)).one().is_deleted is False
    d = client.get(f"/api/fs/statements/{sid}", headers=viewer).json()
    ca = next(n for n in d["tree"] if n["children"])["children"][0]
    ar = next(c for c in ca["children"] if c["id"] == str(ar_id))
    assert D(ar["amount"]) == D(200) and d["validation"]["ok"] is True

    def ids(tree):
        for n in tree:
            yield n["id"]
            yield from ids(n["children"])
    in_2118 = client.get("/api/fs/accounts", params={"statement_type": "BS", "fiscal_year": 2118}, headers=viewer)
    in_2119 = client.get("/api/fs/accounts", params={"statement_type": "BS", "fiscal_year": 2119}, headers=viewer)
    assert str(ar_id) in set(ids(in_2118.json()))
    assert str(ar_id) not in set(ids(in_2119.json()))


# ── 9. tenant 격리 ─────────────────────────────────────────

def test_tenant_isolation(client: TestClient, viewer: dict) -> None:
    other_id = uuid4()
    with session(None) as db:
        db.add(Tenant(id=other_id, name="다른회사", code=f"FS-{other_id.hex[:6]}", is_active=True))
        db.commit()
    with session(other_id) as db:
        o_acc = _bs_accounts(db)
        o_st, _ = _bs(db, 2120, acc=o_acc)
        o_sid, o_root = o_st.id, o_acc["A"].id
    with session() as db:
        assert o_root not in {a.id for a, _ in svc.account_tree_rows(db, "BS")}
        mine = svc.create_account(db, statement_type="BS", name="x", section="asset")
        with pytest.raises(svc.FsNotFoundError):             # 다른 테넌트 계정을 부모로 못 건다
            svc.set_parent(db, mine, o_root)
        db.rollback()
    assert client.get(f"/api/fs/statements/{o_sid}", headers=viewer).status_code == 404
    assert o_sid not in {s["id"] for s in client.get("/api/fs/statements", headers=viewer).json()}


# ── 10. 감사 컬럼 (13.9-51) ────────────────────────────────

def test_audit_columns_record_user_id(client: TestClient, mgr: dict) -> None:
    with session() as db:
        st, _ = _bs(db, 2121)
        sid = st.id
        assert st.created_by == "system:test"
    assert client.post(f"/api/fs/statements/{sid}/finalize", headers=mgr, json={}).status_code == 200
    uid = str(_user_id("fs-mgr@acme.example"))
    with session() as db:
        st = db.scalars(select(FsStatement).where(FsStatement.id == sid)).one()
        ev = db.scalars(select(FsStatementStatusEvent).where(FsStatementStatusEvent.statement_id == sid)).one()
        assert st.updated_by == uid
        assert ev.created_by == uid and str(ev.actor_id) == uid


def test_meta(client: TestClient, viewer: dict) -> None:
    m = client.get("/api/fs/meta", headers=viewer).json()
    assert [o["value"] for o in m["statement_types"]] == ["BS", "PL", "CF", "SCE"]
    assert "liability_equity" in m["sections_by_statement"]["BS"]
    assert client.get("/api/fs/accounts", params={"statement_type": "NOTE"}, headers=viewer).status_code == 422


def test_update_tolerance(client: TestClient, mgr: dict, viewer: dict) -> None:
    """허용 오차 설정(8-D) — draft 에서만, 음수 거부, icfr_manager 전용."""
    with session() as db:
        st, _ = _bs(db, 2122, {**BALANCED, "A": 301})           # 자산총계 1 차이
        sid = st.id
    r = client.patch(f"/api/fs/statements/{sid}", headers=mgr, json={"tolerance": "1"})
    assert r.status_code == 200, r.text
    assert r.json()["validation"]["ok"] and D(r.json()["tolerance"]) == D(1)
    assert client.patch(f"/api/fs/statements/{sid}", headers=mgr, json={"tolerance": "-1"}).status_code == 422
    assert client.patch(f"/api/fs/statements/{sid}", headers=viewer, json={"tolerance": "0"}).status_code == 403
    assert client.post(f"/api/fs/statements/{sid}/finalize", headers=mgr, json={}).status_code == 200
    assert client.patch(f"/api/fs/statements/{sid}", headers=mgr, json={"tolerance": "0"}).status_code == 409
