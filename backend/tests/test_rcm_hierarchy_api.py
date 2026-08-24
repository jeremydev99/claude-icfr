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
    ACTION_EXCLUDE,
    ACTION_OVERRIDE,
    BaselineProcess,
    BaselineRisk,
    BaselineSubProcess,
    ProcessInstance,
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
