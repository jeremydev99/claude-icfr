"""어서션 junction overlay 검증 (2-A-4-4, ADR-0029 §2.3·§2.4).

핵심은 두 가지다.
- test_remove_baseline_link_keeps_baseline_row — baseline junction 불변(overlay 만 기록)
- test_readd_removed_link_drops_remove_record — 떼었다 붙이면 remove 가 사라지고
  **add 로 전환되지 않는다**. 이게 없으면 add 로 전환하는 구현도 나머지를 전부 통과한다.
"""
from fastapi.testclient import TestClient

from app.core.tenant_context import DEFAULT_TENANT_ID, reset_active_tenant, set_active_tenant
from app.models.rcm_baseline import (
    ASSERTION_ACTION_ADD,
    ASSERTION_ACTION_REMOVE,
    BaselineControl,
    BaselineControlAssertion,
    BaselineProcess,
    BaselineRisk,
    BaselineRiskCategory,
    BaselineSubProcess,
    ControlAssertionInstance,
)
from tests.conftest import TestingSessionLocal


def _headers(client: TestClient) -> dict:
    resp = client.post("/api/auth/login", data={"username": "admin@acme.example", "password": "admin123"})
    assert resp.status_code == 200
    return {"Authorization": "Bearer " + resp.json()["access_token"]}


def _baseline_chain(db, suffix: str, cat_codes: tuple[str, ...], linked: tuple[str, ...] = ()):
    """baseline 4단 체인 + 어서션 카테고리. linked 에 준 코드만 baseline 연결로 만든다."""
    p = BaselineProcess(code=f"AO{suffix}-P", name="P")
    db.add(p)
    db.flush()
    sp = BaselineSubProcess(code=f"AO{suffix}-SP", name="SP", process_id=p.id)
    db.add(sp)
    db.flush()
    r = BaselineRisk(code=f"AO{suffix}-R", description="R", assessment_level="LR", sub_process_id=sp.id)
    db.add(r)
    db.flush()
    c = BaselineControl(code=f"AO{suffix}-C", name=f"AO{suffix} 통제", risk_id=r.id)
    db.add(c)
    db.flush()
    cats = {}
    for code in cat_codes:
        cat = BaselineRiskCategory(code=f"{code}{suffix}", name=code)
        db.add(cat)
        db.flush()
        cats[code] = cat
    for code in linked:
        db.add(BaselineControlAssertion(baseline_control_id=c.id, baseline_risk_category_id=cats[code].id))
    db.commit()
    return c, cats


def _assertions_of(client: TestClient, h: dict, code: str) -> list[str]:
    """search 응답의 assertions 배열 — 쓴 것이 읽히는지 보는 지점(상세는 assertions 미포함)."""
    resp = client.get("/api/rcm/controls/search", params={"q": code}, headers=h)
    assert resp.status_code == 200, resp.text
    items = [i for i in resp.json()["items"] if i["code"] == code]
    assert len(items) == 1, f"{code} not found in search"
    return items[0]["assertions"]


def _instances(db, control_attr: str, control_id, cat_id) -> list[ControlAssertionInstance]:
    """해당 쌍의 overlay 행 전부 — is_deleted 로 거르지 않는다(재활성화 대상까지 본다)."""
    return db.query(ControlAssertionInstance).filter(
        getattr(ControlAssertionInstance, control_attr) == control_id,
        ControlAssertionInstance.baseline_risk_category_id == cat_id,
    ).all()


# ── §6-1 ──────────────────────────────────────────────────

def test_add_link_absent_in_baseline_creates_add_instance(client: TestClient) -> None:
    """§6-1 — baseline 에 없는 연결 추가 → add 레코드 생성 + 조회 반영."""
    h = _headers(client)
    db = TestingSessionLocal()
    tok = set_active_tenant(DEFAULT_TENANT_ID)
    try:
        c, cats = _baseline_chain(db, "1", ("E", "C"), linked=("E",))
        assert _assertions_of(client, h, c.code) == ["E1"]

        resp = client.post("/api/rcm/control-assertions",
                           json={"control_id": str(c.id), "risk_category_id": str(cats["C"].id)}, headers=h)
        assert resp.status_code == 201, resp.text

        rows = _instances(db, "control_baseline_id", c.id, cats["C"].id)
        assert len(rows) == 1
        assert rows[0].action == ASSERTION_ACTION_ADD
        assert rows[0].is_deleted is False
        assert _assertions_of(client, h, c.code) == ["C1", "E1"]
    finally:
        reset_active_tenant(tok)
        db.close()


# ── §6-2 ──────────────────────────────────────────────────

def test_remove_baseline_link_keeps_baseline_row(client: TestClient) -> None:
    """§6-2 — baseline 연결 제거 → remove 레코드 생성. **baseline junction 행은 불변.**"""
    h = _headers(client)
    db = TestingSessionLocal()
    tok = set_active_tenant(DEFAULT_TENANT_ID)
    try:
        c, cats = _baseline_chain(db, "2", ("E",), linked=("E",))
        link = db.query(BaselineControlAssertion).filter(
            BaselineControlAssertion.baseline_control_id == c.id).one()
        link_id = link.id

        resp = client.delete(f"/api/rcm/control-assertions/{link_id}", headers=h)
        assert resp.status_code == 204, resp.text

        rows = _instances(db, "control_baseline_id", c.id, cats["E"].id)
        assert len(rows) == 1
        assert rows[0].action == ASSERTION_ACTION_REMOVE
        assert rows[0].is_deleted is False

        db.expire_all()
        after = db.query(BaselineControlAssertion).filter(BaselineControlAssertion.id == link_id).one()
        assert after.is_deleted is False                          # 원본 불변
        assert after.baseline_risk_category_id == cats["E"].id
        assert _assertions_of(client, h, c.code) == []
    finally:
        reset_active_tenant(tok)
        db.close()


# ── §6-3 (핵심) ────────────────────────────────────────────

def test_readd_removed_link_drops_remove_record(client: TestClient) -> None:
    """§6-3 — 떼었다 다시 붙이면 remove 가 사라지고 baseline 상태로 복귀한다.

    **add 레코드로 전환되지 않는다** — baseline 에 이미 있는 연결을 overlay 에도 적으면
    같은 상태가 두 가지로 표현된다. 행 자체는 재활성화 대상으로 남긴다(유니크 제약).
    """
    h = _headers(client)
    db = TestingSessionLocal()
    tok = set_active_tenant(DEFAULT_TENANT_ID)
    try:
        c, cats = _baseline_chain(db, "3", ("E",), linked=("E",))
        link = db.query(BaselineControlAssertion).filter(
            BaselineControlAssertion.baseline_control_id == c.id).one()

        assert client.delete(f"/api/rcm/control-assertions/{link.id}", headers=h).status_code == 204
        assert _assertions_of(client, h, c.code) == []

        resp = client.post("/api/rcm/control-assertions",
                           json={"control_id": str(c.id), "risk_category_id": str(cats["E"].id)}, headers=h)
        assert resp.status_code == 201, resp.text
        assert resp.json()["id"] == str(link.id)            # baseline 연결로 복귀 — 새 id 가 아니다

        db.expire_all()
        rows = _instances(db, "control_baseline_id", c.id, cats["E"].id)
        assert len(rows) == 1                               # 재활성화 대상으로 존치
        assert rows[0].is_deleted is True                   # 조회에서는 부재
        assert rows[0].action == ASSERTION_ACTION_REMOVE    # add 로 전환하지 않는다
        assert _assertions_of(client, h, c.code) == ["E3"]
    finally:
        reset_active_tenant(tok)
        db.close()


def test_remove_after_readd_reuses_row(client: TestClient) -> None:
    """§2.1 실측 반영 — remove → 재추가 → 다시 remove 가 유니크 제약을 위반하지 않는다.

    소프트 삭제된 행이 (tenant, 통제, 어서션) 자리를 계속 점유하므로 새 행을 만들면
    제약 위반이다. 행 재사용(재활성화)이 지켜지는지 본다.
    """
    h = _headers(client)
    db = TestingSessionLocal()
    tok = set_active_tenant(DEFAULT_TENANT_ID)
    try:
        c, cats = _baseline_chain(db, "4", ("E",), linked=("E",))
        link = db.query(BaselineControlAssertion).filter(
            BaselineControlAssertion.baseline_control_id == c.id).one()

        assert client.delete(f"/api/rcm/control-assertions/{link.id}", headers=h).status_code == 204
        assert client.post("/api/rcm/control-assertions",
                           json={"control_id": str(c.id), "risk_category_id": str(cats["E"].id)},
                           headers=h).status_code == 201
        assert client.delete(f"/api/rcm/control-assertions/{link.id}", headers=h).status_code == 204

        db.expire_all()
        rows = _instances(db, "control_baseline_id", c.id, cats["E"].id)
        assert len(rows) == 1
        assert rows[0].action == ASSERTION_ACTION_REMOVE
        assert rows[0].is_deleted is False
        assert _assertions_of(client, h, c.code) == []
    finally:
        reset_active_tenant(tok)
        db.close()


# ── §6-4 ──────────────────────────────────────────────────

def test_added_control_link_hangs_on_control_instance_id(client: TestClient) -> None:
    """§6-4 — tenant 신규 통제(add)의 연결은 control_instance_id 에 매달린다."""
    h = _headers(client)
    db = TestingSessionLocal()
    tok = set_active_tenant(DEFAULT_TENANT_ID)
    try:
        _, cats = _baseline_chain(db, "5", ("E",))
        risk_id = db.query(BaselineRisk).filter(BaselineRisk.code == "AO5-R").one().id
        cat_id = cats["E"].id
    finally:
        reset_active_tenant(tok)
        db.close()

    created = client.post("/api/rcm/controls", json={
        "code": "AO5-NEW", "name": "AO5 신규통제", "risk_id": str(risk_id), "frequency": "M",
    }, headers=h)
    assert created.status_code == 201, created.text
    ctrl_id = created.json()["id"]
    assert created.json()["source"] == "tenant"

    resp = client.post("/api/rcm/control-assertions",
                       json={"control_id": ctrl_id, "risk_category_id": str(cat_id)}, headers=h)
    assert resp.status_code == 201, resp.text

    db = TestingSessionLocal()
    tok = set_active_tenant(DEFAULT_TENANT_ID)
    try:
        row = db.query(ControlAssertionInstance).filter(
            ControlAssertionInstance.baseline_risk_category_id == cat_id).one()
        assert str(row.control_instance_id) == ctrl_id
        assert row.control_baseline_id is None          # 이중 FK — 한쪽만 채운다
        assert row.action == ASSERTION_ACTION_ADD
    finally:
        reset_active_tenant(tok)
        db.close()
    assert _assertions_of(client, h, "AO5-NEW") == ["E5"]


# ── §6-5 ──────────────────────────────────────────────────

def test_baseline_control_link_hangs_on_control_baseline_id(client: TestClient) -> None:
    """§6-5 — baseline 통제의 연결은 control_baseline_id 에 매달린다(정체성은 baseline 쪽)."""
    h = _headers(client)
    db = TestingSessionLocal()
    tok = set_active_tenant(DEFAULT_TENANT_ID)
    try:
        c, cats = _baseline_chain(db, "6", ("E",))
        resp = client.post("/api/rcm/control-assertions",
                           json={"control_id": str(c.id), "risk_category_id": str(cats["E"].id)}, headers=h)
        assert resp.status_code == 201, resp.text

        row = db.query(ControlAssertionInstance).filter(
            ControlAssertionInstance.baseline_risk_category_id == cats["E"].id).one()
        assert row.control_baseline_id == c.id
        assert row.control_instance_id is None
    finally:
        reset_active_tenant(tok)
        db.close()


# ── §6-6 ──────────────────────────────────────────────────

def test_link_edit_on_excluded_control_survives_restore(client: TestClient) -> None:
    """§6-6 — 제외된 통제의 연결 편집이 허용되고, 통제 복원 시 그 편집이 반영된다.

    제외는 되돌릴 수 있는 상태다(ADR-0029 §2.2). "조회에서 안 보인다"와 "편집 불가"는 다르다.
    """
    h = _headers(client)
    db = TestingSessionLocal()
    tok = set_active_tenant(DEFAULT_TENANT_ID)
    try:
        c, cats = _baseline_chain(db, "7", ("E", "C"), linked=("E",))
        cat_c_id, control_id = cats["C"].id, c.id
    finally:
        reset_active_tenant(tok)
        db.close()

    assert client.delete(f"/api/rcm/controls/{control_id}", headers=h).status_code == 204
    assert client.get(f"/api/rcm/controls/{control_id}", headers=h).status_code == 404   # §2.4 제외

    resp = client.post("/api/rcm/control-assertions",
                       json={"control_id": str(control_id), "risk_category_id": str(cat_c_id)}, headers=h)
    assert resp.status_code == 201, resp.text            # 제외 중에도 편집 허용

    restored = client.patch(f"/api/rcm/controls/{control_id}", json={"name": "AO7 복원"}, headers=h)
    assert restored.status_code == 200, restored.text
    assert _assertions_of(client, h, "AO7-C") == ["C7", "E7"]   # 제외 중 편집분이 살아난다


def test_excluded_control_links_drop_from_list(client: TestClient) -> None:
    """§2.4 — 통제가 effective 제외면 그 연결도 목록에서 빠진다(레코드는 건드리지 않는다)."""
    h = _headers(client)
    db = TestingSessionLocal()
    tok = set_active_tenant(DEFAULT_TENANT_ID)
    try:
        c, _ = _baseline_chain(db, "8", ("E",), linked=("E",))
        link_uuid = db.query(BaselineControlAssertion).filter(
            BaselineControlAssertion.baseline_control_id == c.id).one().id
        link_id, control_id = str(link_uuid), c.id
    finally:
        reset_active_tenant(tok)
        db.close()

    listed = client.get("/api/rcm/control-assertions?limit=500", headers=h).json()["items"]
    assert link_id in {i["id"] for i in listed}

    assert client.delete(f"/api/rcm/controls/{control_id}", headers=h).status_code == 204
    listed = client.get("/api/rcm/control-assertions?limit=500", headers=h).json()["items"]
    assert link_id not in {i["id"] for i in listed}

    db = TestingSessionLocal()
    try:   # 연결 레코드 자체는 변경되지 않았다
        assert db.query(BaselineControlAssertion).filter(
            BaselineControlAssertion.id == link_uuid).one().is_deleted is False
    finally:
        db.close()
