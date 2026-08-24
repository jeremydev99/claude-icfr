"""cascade 시맨틱 검증 (ADR-0029 §5) — 2-A-4-3.

§2.1 상위 제외 목록을 한 번 읽어 하위를 거른다(재귀 조회 없음).
§2.2 "상위로 인한 제외"는 **저장하지 않는다** — 조회 시점 계산.

핵심은 test_child_exclusion_survives_parent_restore (§5-3).
이것이 없으면 제외 상태를 컬럼에 저장하는 구현으로도 §5-2 만 통과해버린다.
"""
from uuid import UUID

from fastapi.testclient import TestClient

from app.core.tenant_context import DEFAULT_TENANT_ID, reset_active_tenant, set_active_tenant
from app.models.rcm_baseline import (
    ACTION_ADD,
    ACTION_EXCLUDE,
    BaselineControl,
    BaselineControlAssertion,
    BaselineProcess,
    BaselineRisk,
    BaselineRiskCategory,
    BaselineSubProcess,
    ProcessInstance,
    RiskInstance,
    SubProcessInstance,
)
from app.services.control_resolver import resolve_controls, resolve_hierarchy
from tests.conftest import TestingSessionLocal


def _headers(client: TestClient) -> dict:
    resp = client.post("/api/auth/login", data={"username": "admin@acme.example", "password": "admin123"})
    assert resp.status_code == 200
    return {"Authorization": "Bearer " + resp.json()["access_token"]}


def _chain(db, suffix):
    """baseline 4단 체인 (process→sub→risk→control)."""
    p = BaselineProcess(code=f"CS{suffix}-P", name="P")
    db.add(p)
    db.flush()
    sp = BaselineSubProcess(code=f"CS{suffix}-SP", name="SP", process_id=p.id)
    db.add(sp)
    db.flush()
    r = BaselineRisk(code=f"CS{suffix}-R", description="R", assessment_level="LR", sub_process_id=sp.id)
    db.add(r)
    db.flush()
    c = BaselineControl(code=f"CS{suffix}-C", name="C", risk_id=r.id)
    db.add(c)
    db.commit()
    return p, sp, r, c


def _codes(db):
    """resolve 결과의 계층별 code 집합 (cascade 적용 후)."""
    procs, subs, risks = resolve_hierarchy(db)
    return (
        {x["code"] for x in procs},
        {x["code"] for x in subs},
        {x["code"] for x in risks},
        {x["code"] for x in resolve_controls(db)},
    )


# ── §5-1 ──────────────────────────────────────────────────

def test_processes_list_returns_all_baseline(client: TestClient) -> None:
    """§5-1 — baseline 프로세스가 전부 목록에 나온다(운영 0건 회귀 방지)."""
    db = TestingSessionLocal()
    tok = set_active_tenant(DEFAULT_TENANT_ID)
    try:
        for i in range(3):
            db.add(BaselineProcess(code=f"CS1-P{i}", name=f"P{i}"))
        db.commit()
        expected = {f"CS1-P{i}" for i in range(3)}
    finally:
        reset_active_tenant(tok)
        db.close()

    body = client.get("/api/rcm/processes?limit=500", headers=_headers(client)).json()
    codes = {i["code"] for i in body["items"]}
    assert expected <= codes
    assert body["total"] >= 3


# ── §5-2 ──────────────────────────────────────────────────

def test_parent_exclusion_cascades_to_children(client: TestClient) -> None:
    """§5-2 — 상위 제외 시 하위(sub/risk/control)가 effective 제외로 계산된다."""
    db = TestingSessionLocal()
    tok = set_active_tenant(DEFAULT_TENANT_ID)
    try:
        p, sp, r, c = _chain(db, "2")
        p_codes, sp_codes, r_codes, c_codes = _codes(db)
        assert "CS2-P" in p_codes and "CS2-SP" in sp_codes
        assert "CS2-R" in r_codes and "CS2-C" in c_codes

        db.add(ProcessInstance(baseline_process_id=p.id, action=ACTION_EXCLUDE))
        db.commit()

        p_codes, sp_codes, r_codes, c_codes = _codes(db)
        assert "CS2-P" not in p_codes
        assert "CS2-SP" not in sp_codes      # cascade
        assert "CS2-R" not in r_codes
        assert "CS2-C" not in c_codes
    finally:
        reset_active_tenant(tok)
        db.close()


def test_cascade_does_not_write_to_children(client: TestClient) -> None:
    """§2.2 — cascade 는 하위 레코드를 물리적으로 만들거나 바꾸지 않는다."""
    db = TestingSessionLocal()
    tok = set_active_tenant(DEFAULT_TENANT_ID)
    try:
        p, sp, r, c = _chain(db, "2B")
        p_id = p.id
        before_sub = db.query(SubProcessInstance).count()
        before_risk = db.query(RiskInstance).count()
    finally:
        reset_active_tenant(tok)
        db.close()

    client.delete(f"/api/rcm/processes/{p_id}", headers=_headers(client))

    db = TestingSessionLocal()
    tok = set_active_tenant(DEFAULT_TENANT_ID)
    try:
        assert db.query(SubProcessInstance).count() == before_sub, "하위에 제외 상태를 저장했다(§2.2 위반)"
        assert db.query(RiskInstance).count() == before_risk, "하위에 제외 상태를 저장했다(§2.2 위반)"
    finally:
        reset_active_tenant(tok)
        db.close()


# ── §5-3 (핵심) ───────────────────────────────────────────

def test_child_exclusion_survives_parent_restore(client: TestClient) -> None:
    """§5-3 — 하위 개별 제외 → 상위 제외 → 상위 복원 시 하위 개별 제외가 **보존**된다.

    제외 상태를 하위에 저장하는 구현이면 상위 복원 시 하위가 함께 살아나거나(덮어씀),
    상위 제외 때 기록한 값이 남아 형제까지 죽는다. 둘 다 이 테스트에서 걸린다.
    """
    db = TestingSessionLocal()
    tok = set_active_tenant(DEFAULT_TENANT_ID)
    try:
        p = BaselineProcess(code="CS3-P", name="P")
        db.add(p)
        db.flush()
        sp_keep = BaselineSubProcess(code="CS3-SP-KEEP", name="유지", process_id=p.id)
        sp_drop = BaselineSubProcess(code="CS3-SP-DROP", name="개별제외", process_id=p.id)
        db.add_all([sp_keep, sp_drop])
        db.commit()
        p_id, drop_id = p.id, sp_drop.id
    finally:
        reset_active_tenant(tok)
        db.close()

    h = _headers(client)
    assert client.delete(f"/api/rcm/sub-processes/{drop_id}", headers=h).status_code == 204

    db = TestingSessionLocal()
    tok = set_active_tenant(DEFAULT_TENANT_ID)
    try:
        # 1) 하위 하나만 개별 제외된 상태
        _, subs, _, _ = _codes(db)
        assert "CS3-SP-KEEP" in subs and "CS3-SP-DROP" not in subs
    finally:
        reset_active_tenant(tok)
        db.close()

    # 2) 상위 제외 → 둘 다 사라진다
    assert client.delete(f"/api/rcm/processes/{p_id}", headers=h).status_code == 204

    db = TestingSessionLocal()
    tok = set_active_tenant(DEFAULT_TENANT_ID)
    try:
        _, subs, _, _ = _codes(db)
        assert "CS3-SP-KEEP" not in subs and "CS3-SP-DROP" not in subs

        # 3) 상위 복원 (exclude instance 제거 = 표준 채택 상태로 되돌림)
        inst = db.query(ProcessInstance).filter(ProcessInstance.baseline_process_id == p_id).one()
        db.delete(inst)
        db.commit()

        # 4) 개별 제외는 보존, 형제는 복원
        _, subs, _, _ = _codes(db)
        assert "CS3-SP-KEEP" in subs, "상위 복원인데 형제가 살아나지 않았다"
        assert "CS3-SP-DROP" not in subs, "상위 복원이 하위 개별 제외를 덮어썼다(§2.2 위반)"
    finally:
        reset_active_tenant(tok)
        db.close()


# ── §5-4 ──────────────────────────────────────────────────

def test_control_exclusion_drops_its_assertions(client: TestClient) -> None:
    """§5-4 — 통제가 제외되면 그 통제의 어서션 연결도 결과에서 함께 사라진다.

    어서션은 junction(baseline_control_assertions + control_assertion_instances)으로
    통제 정체성 id 에 매달리므로, 통제가 resolve 결과에서 빠지면 어서션도 노출되지 않는다.
    """
    db = TestingSessionLocal()
    tok = set_active_tenant(DEFAULT_TENANT_ID)
    try:
        p, sp, r, c = _chain(db, "4")
        rc = BaselineRiskCategory(code="CS4-E", name="실재성")
        db.add(rc)
        db.flush()
        db.add(BaselineControlAssertion(baseline_control_id=c.id, baseline_risk_category_id=rc.id))
        db.commit()
        c_id = c.id

        rows = {x["code"]: x for x in resolve_controls(db)}
        assert "CS4-E" in rows["CS4-C"]["assertions"]
    finally:
        reset_active_tenant(tok)
        db.close()

    client.delete(f"/api/rcm/controls/{c_id}", headers=_headers(client))

    db = TestingSessionLocal()
    tok = set_active_tenant(DEFAULT_TENANT_ID)
    try:
        rows = {x["code"]: x for x in resolve_controls(db)}
        assert "CS4-C" not in rows
    finally:
        reset_active_tenant(tok)
        db.close()


def test_cascade_hides_assertions_of_cascaded_control(client: TestClient) -> None:
    """§5-4 보강 — 상위 제외로 cascade 된 통제의 어서션도 노출되지 않는다."""
    db = TestingSessionLocal()
    tok = set_active_tenant(DEFAULT_TENANT_ID)
    try:
        p, sp, r, c = _chain(db, "4B")
        p_id = p.id
        rc = BaselineRiskCategory(code="CS4B-C", name="완전성")
        db.add(rc)
        db.flush()
        db.add(BaselineControlAssertion(baseline_control_id=c.id, baseline_risk_category_id=rc.id))
        db.commit()

        rows = {x["code"]: x for x in resolve_controls(db)}
        assert "CS4B-C" in rows["CS4B-C"]["assertions"]
    finally:
        reset_active_tenant(tok)
        db.close()

    client.delete(f"/api/rcm/processes/{p_id}", headers=_headers(client))

    db = TestingSessionLocal()
    tok = set_active_tenant(DEFAULT_TENANT_ID)
    try:
        assert "CS4B-C" not in {x["code"] for x in resolve_controls(db)}
    finally:
        reset_active_tenant(tok)
        db.close()


# ── §5-5 ──────────────────────────────────────────────────

def test_added_hierarchy_follows_same_cascade_rules(client: TestClient) -> None:
    """§5-5 — action='add' 항목도 §5-2·§5-3 이 동일하게 동작한다."""
    h = _headers(client)
    pid = client.post("/api/rcm/processes", json={"code": "CS5-P", "name": "회사P"}, headers=h).json()["id"]
    client.post("/api/rcm/sub-processes",
                json={"code": "CS5-SP-KEEP", "name": "유지", "process_id": pid}, headers=h)
    drop = client.post("/api/rcm/sub-processes",
                       json={"code": "CS5-SP-DROP", "name": "개별제외", "process_id": pid}, headers=h).json()["id"]

    # §5-2 — 하위 개별 제외 후 상위 제외 → 전부 사라짐
    client.delete(f"/api/rcm/sub-processes/{drop}", headers=h)

    db = TestingSessionLocal()
    tok = set_active_tenant(DEFAULT_TENANT_ID)
    try:
        _, subs, _, _ = _codes(db)
        assert "CS5-SP-KEEP" in subs and "CS5-SP-DROP" not in subs
    finally:
        reset_active_tenant(tok)
        db.close()

    client.delete(f"/api/rcm/processes/{pid}", headers=h)

    db = TestingSessionLocal()
    tok = set_active_tenant(DEFAULT_TENANT_ID)
    try:
        _, subs, _, _ = _codes(db)
        assert "CS5-SP-KEEP" not in subs and "CS5-SP-DROP" not in subs

        # §5-3 — 상위 복원(soft delete 해제) 시 하위 개별 제외 보존
        # pid 는 JSON 응답의 문자열 — PG_UUID 컬럼 비교에는 UUID 객체가 필요하다.
        inst = db.query(ProcessInstance).filter(ProcessInstance.id == UUID(pid)).one()
        assert inst.action == ACTION_ADD and inst.is_deleted is True
        inst.is_deleted = False
        db.commit()

        _, subs, _, _ = _codes(db)
        assert "CS5-SP-KEEP" in subs, "상위 복원인데 형제가 살아나지 않았다"
        assert "CS5-SP-DROP" not in subs, "상위 복원이 하위 개별 제외를 덮어썼다(§2.2 위반)"
    finally:
        reset_active_tenant(tok)
        db.close()
