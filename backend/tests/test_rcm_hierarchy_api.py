"""상위 3계층(process/sub_process/risk) API resolver 전환 검증 (2-A-4-3, ADR-0029).

조회 계층 — 목록·상세가 레거시 테이블이 아니라 resolver(baseline−exclude+override+add)를
읽는지, 그리고 통제와 동일한 flat source envelope 를 내는지 확인한다.

**이 파일이 막는 회귀**: 운영에서 레거시 테이블이 비어 상위 3계층이 0건이 되던 상태
(ClaudeICFR.md 13.7 정정). 로컬 레거시 잔존 데이터에 가려지지 않도록 레거시 테이블에는
아무것도 넣지 않고 baseline 만으로 검증한다.
"""
from fastapi.testclient import TestClient

from app.core.tenant_context import DEFAULT_TENANT_ID, reset_active_tenant, set_active_tenant
from app.models.rcm_baseline import (
    ACTION_ADD,
    ACTION_ADOPT,
    ACTION_EXCLUDE,
    ACTION_OVERRIDE,
    BaselineProcess,
    BaselineRisk,
    BaselineSubProcess,
    ProcessInstance,
    SubProcessInstance,
)
from tests.conftest import TestingSessionLocal


def _headers(client: TestClient) -> dict:
    resp = client.post("/api/auth/login", data={"username": "admin@acme.example", "password": "admin123"})
    assert resp.status_code == 200
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _seed_chain(db, suffix):
    """baseline 3계층 체인 — 레거시 테이블은 건드리지 않는다."""
    p = BaselineProcess(code=f"H{suffix}-P", name="표준 프로세스")
    db.add(p)
    db.flush()
    sp = BaselineSubProcess(code=f"H{suffix}-SP", name="표준 하위프로세스", process_id=p.id)
    db.add(sp)
    db.flush()
    r = BaselineRisk(code=f"H{suffix}-R", description="표준 위험", sub_process_id=sp.id)
    db.add(r)
    db.commit()
    return p, sp, r


def test_processes_list_reads_baseline(client: TestClient) -> None:
    """레거시 processes 가 비어 있어도 baseline 이 목록에 나온다 (운영 0건 회귀 방지)."""
    db = TestingSessionLocal()
    tok = set_active_tenant(DEFAULT_TENANT_ID)
    try:
        p, sp, r = _seed_chain(db, "L1")
    finally:
        reset_active_tenant(tok)
        db.close()

    resp = client.get("/api/rcm/processes?limit=200", headers=_headers(client))
    assert resp.status_code == 200
    body = resp.json()
    codes = {i["code"] for i in body["items"]}
    assert "HL1-P" in codes
    assert body["total"] >= 1

    resp = client.get("/api/rcm/sub-processes?limit=200", headers=_headers(client))
    assert "HL1-SP" in {i["code"] for i in resp.json()["items"]}
    resp = client.get("/api/rcm/risks?limit=200", headers=_headers(client))
    assert "HL1-R" in {i["code"] for i in resp.json()["items"]}


def test_hierarchy_list_source_envelope(client: TestClient) -> None:
    """3계층 응답이 통제와 동일한 flat envelope(source/baseline_id/is_overridden)를 낸다."""
    db = TestingSessionLocal()
    tok = set_active_tenant(DEFAULT_TENANT_ID)
    try:
        p, sp, r = _seed_chain(db, "L2")
        po = BaselineProcess(code="HL2-OVR", name="표준명")
        db.add(po)
        db.commit()
        po_id = po.id
        db.add(ProcessInstance(baseline_process_id=po_id, action=ACTION_OVERRIDE, name="회사명"))
        db.add(ProcessInstance(baseline_process_id=None, action=ACTION_ADD, code="HL2-ADD", name="회사 프로세스"))
        db.commit()
    finally:
        reset_active_tenant(tok)
        db.close()

    items = {i["code"]: i for i in client.get("/api/rcm/processes?limit=200", headers=_headers(client)).json()["items"]}

    adopt = items["HL2-P"]
    assert adopt["source"] == "baseline" and adopt["is_overridden"] is False
    assert adopt["baseline_id"] == adopt["id"]  # 정체성 = baseline

    ovr = items["HL2-OVR"]
    assert ovr["source"] == "baseline" and ovr["is_overridden"] is True
    assert ovr["name"] == "회사명"                      # override 값이 병합됨
    assert ovr["baseline_id"] == str(po_id)

    add = items["HL2-ADD"]
    assert add["source"] == "tenant" and add["baseline_id"] is None and add["is_overridden"] is False

    # 하위 계층도 같은 계약
    sub = {i["code"]: i for i in client.get("/api/rcm/sub-processes?limit=200", headers=_headers(client)).json()["items"]}["HL2-SP"]
    assert {"source", "baseline_id", "is_overridden"} <= set(sub)
    risk = {i["code"]: i for i in client.get("/api/rcm/risks?limit=200", headers=_headers(client)).json()["items"]}["HL2-R"]
    assert {"source", "baseline_id", "is_overridden"} <= set(risk)


def test_hierarchy_detail_reads_resolver(client: TestClient) -> None:
    """상세도 resolver 경유 — 정체성 id 로 조회되고, 제외된 항목은 404."""
    db = TestingSessionLocal()
    tok = set_active_tenant(DEFAULT_TENANT_ID)
    try:
        p, sp, r = _seed_chain(db, "L3")
        p_id, sp_id, r_id = p.id, sp.id, r.id
        px = BaselineProcess(code="HL3-X", name="제외 대상")
        db.add(px)
        db.commit()
        px_id = px.id
        db.add(ProcessInstance(baseline_process_id=px_id, action=ACTION_EXCLUDE))
        db.commit()
    finally:
        reset_active_tenant(tok)
        db.close()

    h = _headers(client)
    assert client.get(f"/api/rcm/processes/{p_id}", headers=h).json()["code"] == "HL3-P"
    assert client.get(f"/api/rcm/sub-processes/{sp_id}", headers=h).json()["code"] == "HL3-SP"
    assert client.get(f"/api/rcm/risks/{r_id}", headers=h).json()["code"] == "HL3-R"
    # exclude 된 baseline 은 목록에서 빠지므로 상세도 404 (조회 경로 일관)
    assert client.get(f"/api/rcm/processes/{px_id}", headers=h).status_code == 404


def test_sub_process_filter_by_parent(client: TestClient) -> None:
    """process_id 필터가 resolver 결과 위에서 동작한다 (기존 쿼리 파라미터 계약 유지)."""
    db = TestingSessionLocal()
    tok = set_active_tenant(DEFAULT_TENANT_ID)
    try:
        p, sp, r = _seed_chain(db, "L4")
        p_id = p.id
        other = BaselineProcess(code="HL4-P2", name="다른 프로세스")
        db.add(other)
        db.flush()
        db.add(BaselineSubProcess(code="HL4-SP2", name="다른 하위", process_id=other.id))
        db.commit()
    finally:
        reset_active_tenant(tok)
        db.close()

    resp = client.get(f"/api/rcm/sub-processes?process_id={p_id}&limit=200", headers=_headers(client))
    codes = {i["code"] for i in resp.json()["items"]}
    assert "HL4-SP" in codes and "HL4-SP2" not in codes


def test_legacy_tables_untouched_by_reads(client: TestClient) -> None:
    """조회 전환이 레거시 테이블에 의존하지 않음을 명시적으로 고정한다."""
    from app.models.rcm import Process

    db = TestingSessionLocal()
    tok = set_active_tenant(DEFAULT_TENANT_ID)
    try:
        _seed_chain(db, "L5")
        legacy_count = db.query(Process).count()
    finally:
        reset_active_tenant(tok)
        db.close()

    resp = client.get("/api/rcm/processes?limit=200", headers=_headers(client))
    codes = {i["code"] for i in resp.json()["items"]}
    assert "HL5-P" in codes, "baseline 이 응답에 없다 — resolver 미배선 회귀"
    # 레거시 행 수와 무관하게 baseline 이 나와야 한다(운영은 legacy 0건).
    assert resp.json()["total"] >= 1 and legacy_count >= 0


# ── CRUD overlay 전환 (2-A-4-3 커밋2) ─────────────────────

def test_create_hierarchy_writes_instance_not_legacy(client: TestClient) -> None:
    """POST 는 legacy 테이블이 아니라 instance(action=add)에 쓴다."""
    from app.models.rcm import Process as LegacyProcess

    h = _headers(client)
    resp = client.post("/api/rcm/processes", json={"code": "HC1-P", "name": "회사 프로세스"}, headers=h)
    assert resp.status_code == 201
    body = resp.json()
    assert body["source"] == "tenant" and body["baseline_id"] is None

    db = TestingSessionLocal()
    tok = set_active_tenant(DEFAULT_TENANT_ID)
    try:
        inst = db.query(ProcessInstance).filter(ProcessInstance.code == "HC1-P").one()
        assert inst.action == ACTION_ADD and inst.baseline_process_id is None
        assert db.query(LegacyProcess).filter(LegacyProcess.code == "HC1-P").first() is None
    finally:
        reset_active_tenant(tok)
        db.close()


def test_patch_baseline_creates_override_instance(client: TestClient) -> None:
    """baseline 수정은 원본을 건드리지 않고 override instance 로 기록된다."""
    db = TestingSessionLocal()
    tok = set_active_tenant(DEFAULT_TENANT_ID)
    try:
        p, sp, r = _seed_chain(db, "C2")
        p_id = p.id
    finally:
        reset_active_tenant(tok)
        db.close()

    h = _headers(client)
    resp = client.patch(f"/api/rcm/processes/{p_id}", json={"name": "회사가 바꾼 이름"}, headers=h)
    assert resp.status_code == 200
    assert resp.json()["name"] == "회사가 바꾼 이름"
    assert resp.json()["is_overridden"] is True
    assert resp.json()["id"] == str(p_id)          # 정체성은 baseline 유지

    db = TestingSessionLocal()
    tok = set_active_tenant(DEFAULT_TENANT_ID)
    try:
        assert db.query(BaselineProcess).filter(BaselineProcess.id == p_id).one().name == "표준 프로세스"
        inst = db.query(ProcessInstance).filter(ProcessInstance.baseline_process_id == p_id).one()
        assert inst.action == ACTION_OVERRIDE and inst.name == "회사가 바꾼 이름"
    finally:
        reset_active_tenant(tok)
        db.close()


def test_patch_back_to_baseline_value_reverts_to_adopt(client: TestClient) -> None:
    """override 값이 baseline 과 같아지면 adopt 로 되돌아간다(instance 는 흔적으로 남음)."""
    db = TestingSessionLocal()
    tok = set_active_tenant(DEFAULT_TENANT_ID)
    try:
        p, sp, r = _seed_chain(db, "C3")
        p_id = p.id
    finally:
        reset_active_tenant(tok)
        db.close()

    h = _headers(client)
    client.patch(f"/api/rcm/processes/{p_id}", json={"name": "임시명"}, headers=h)
    resp = client.patch(f"/api/rcm/processes/{p_id}", json={"name": "표준 프로세스"}, headers=h)
    assert resp.status_code == 200 and resp.json()["is_overridden"] is False

    db = TestingSessionLocal()
    tok = set_active_tenant(DEFAULT_TENANT_ID)
    try:
        inst = db.query(ProcessInstance).filter(ProcessInstance.baseline_process_id == p_id).one()
        assert inst.action == ACTION_ADOPT and inst.name is None  # NULL=baseline 따름
    finally:
        reset_active_tenant(tok)
        db.close()


def test_delete_baseline_creates_exclude_and_keeps_original(client: TestClient) -> None:
    """baseline 삭제는 exclude instance — 원본 baseline 행은 그대로 남는다."""
    db = TestingSessionLocal()
    tok = set_active_tenant(DEFAULT_TENANT_ID)
    try:
        p, sp, r = _seed_chain(db, "C4")
        p_id = p.id
    finally:
        reset_active_tenant(tok)
        db.close()

    h = _headers(client)
    assert client.delete(f"/api/rcm/processes/{p_id}", headers=h).status_code == 204
    assert client.get(f"/api/rcm/processes/{p_id}", headers=h).status_code == 404

    db = TestingSessionLocal()
    tok = set_active_tenant(DEFAULT_TENANT_ID)
    try:
        assert db.query(BaselineProcess).filter(BaselineProcess.id == p_id).one().is_deleted is False
        inst = db.query(ProcessInstance).filter(ProcessInstance.baseline_process_id == p_id).one()
        assert inst.action == ACTION_EXCLUDE
    finally:
        reset_active_tenant(tok)
        db.close()


def test_delete_add_instance_soft_deletes(client: TestClient) -> None:
    """회사 add 삭제는 instance soft delete."""
    h = _headers(client)
    pid = client.post("/api/rcm/processes", json={"code": "HC5-P", "name": "회사"}, headers=h).json()["id"]
    assert client.delete(f"/api/rcm/processes/{pid}", headers=h).status_code == 204
    assert client.get(f"/api/rcm/processes/{pid}", headers=h).status_code == 404

    db = TestingSessionLocal()
    tok = set_active_tenant(DEFAULT_TENANT_ID)
    try:
        inst = db.query(ProcessInstance).filter(ProcessInstance.code == "HC5-P").one()
        assert inst.is_deleted is True and inst.action == ACTION_ADD
    finally:
        reset_active_tenant(tok)
        db.close()


def test_create_rejects_code_duplicate_against_baseline(client: TestClient) -> None:
    """add 의 code 가 baseline code 와 겹치면 409 (ADR-0029 §3 — DB 제약이 못 막는 구간)."""
    db = TestingSessionLocal()
    tok = set_active_tenant(DEFAULT_TENANT_ID)
    try:
        _seed_chain(db, "C6")
    finally:
        reset_active_tenant(tok)
        db.close()

    h = _headers(client)
    resp = client.post("/api/rcm/processes", json={"code": "HC6-P", "name": "중복"}, headers=h)
    assert resp.status_code == 409
    assert "표준" in resp.json()["detail"]


def test_create_rejects_code_duplicate_against_instance(client: TestClient) -> None:
    """add 끼리 code 가 겹쳐도 409 (IntegrityError 가 아니라 의미 있는 메시지)."""
    h = _headers(client)
    assert client.post("/api/rcm/processes", json={"code": "HC7-P", "name": "첫번째"}, headers=h).status_code == 201
    resp = client.post("/api/rcm/processes", json={"code": "HC7-P", "name": "두번째"}, headers=h)
    assert resp.status_code == 409
    assert "사용 중" in resp.json()["detail"]


def test_create_sub_process_under_added_parent(client: TestClient) -> None:
    """회사 add 프로세스 밑에 하위프로세스를 add 하면 instance 쪽 이중 FK 로 매핑된다."""
    h = _headers(client)
    pid = client.post("/api/rcm/processes", json={"code": "HC8-P", "name": "회사P"}, headers=h).json()["id"]
    resp = client.post("/api/rcm/sub-processes", json={"code": "HC8-SP", "name": "회사SP", "process_id": pid}, headers=h)
    assert resp.status_code == 201
    assert resp.json()["process_id"] == pid

    db = TestingSessionLocal()
    tok = set_active_tenant(DEFAULT_TENANT_ID)
    try:
        inst = db.query(SubProcessInstance).filter(SubProcessInstance.code == "HC8-SP").one()
        assert inst.process_instance_id is not None and inst.process_baseline_id is None
    finally:
        reset_active_tenant(tok)
        db.close()
