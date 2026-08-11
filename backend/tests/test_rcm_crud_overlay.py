"""Control CRUD baseline/overlay 전환 테스트 (ADR-0027, 2-A-4-1).

6가지 분기 + 되돌리기(adopt 전환) + baseline 불변 + falsy 유효값 검증.
baseline 을 세션 DB 에 직접 시딩(마이그레이션 미실행 환경) 후 API(POST/PATCH/DELETE)로 조작.
tenant 는 client(admin@acme.example) = DEFAULT tenant, baseline 은 전역(IdentityBase).
"""
from uuid import UUID

from fastapi.testclient import TestClient

from app.models.rcm_baseline import (
    BaselineControl, BaselineRisk, BaselineSubProcess, BaselineProcess, ControlInstance,
)
from app.core.tenant_context import set_active_tenant, reset_active_tenant, DEFAULT_TENANT_ID
from tests.conftest import TestingSessionLocal


def _headers(client: TestClient) -> dict:
    resp = client.post("/api/auth/login", data={"username": "admin@acme.example", "password": "admin123"})
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _seed_baseline_control(code: str, **kw) -> str:
    """전역 baseline 통제 1건 시딩 후 id 반환."""
    db = TestingSessionLocal()
    tok = set_active_tenant(DEFAULT_TENANT_ID)
    try:
        bc = BaselineControl(code=code, name=kw.pop("name", "표준통제"), **kw)
        db.add(bc)
        db.commit()
        bid = str(bc.id)
    finally:
        reset_active_tenant(tok)
        db.close()
    return bid


def _seed_baseline_risk(suffix: str) -> str:
    """baseline process→sub→risk 체인 시딩 후 risk id 반환."""
    db = TestingSessionLocal()
    tok = set_active_tenant(DEFAULT_TENANT_ID)
    try:
        p = BaselineProcess(code=f"C41P-{suffix}", name="P")
        db.add(p); db.flush()
        sp = BaselineSubProcess(code=f"C41SP-{suffix}", name="SP", process_id=p.id)
        db.add(sp); db.flush()
        r = BaselineRisk(code=f"C41R-{suffix}", description="R", sub_process_id=sp.id)
        db.add(r); db.commit()
        rid = str(r.id)
    finally:
        reset_active_tenant(tok)
        db.close()
    return rid


def _instance_for(baseline_id: str) -> ControlInstance | None:
    db = TestingSessionLocal()
    tok = set_active_tenant(DEFAULT_TENANT_ID)
    try:
        return db.query(ControlInstance).filter(
            ControlInstance.baseline_control_id == UUID(baseline_id)
        ).first()
    finally:
        reset_active_tenant(tok)
        db.close()


def _baseline_count() -> int:
    db = TestingSessionLocal()
    try:
        return db.query(BaselineControl).count()
    finally:
        db.close()


# ── POST → add instance ────────────────────────────────────

def test_post_creates_add_instance(client: TestClient) -> None:
    h = _headers(client)
    rid = _seed_baseline_risk("ADD")
    resp = client.post("/api/rcm/controls", json={
        "code": "C41-ADD-1", "name": "회사 고유 통제", "risk_id": rid,
        "frequency": "M", "preventive_detective": "D", "auto_manual": "A",
    }, headers=h)
    assert resp.status_code == 201
    body = resp.json()
    assert body["source"] == "tenant"
    assert body["baseline_id"] is None
    assert body["is_overridden"] is False
    assert body["risk_id"] == rid  # baseline risk → risk_baseline_id 로 resolve

    # 목록(search)에 즉시 반영 (write→read 왕복)
    s = client.get("/api/rcm/controls/search", params={"q": "회사 고유 통제"}, headers=h)
    assert "C41-ADD-1" in [c["code"] for c in s.json()["items"]]


# ── PATCH(baseline) → override, 바뀐 필드만 저장 ─────────────

def test_patch_baseline_creates_override_diff(client: TestClient) -> None:
    h = _headers(client)
    bid = _seed_baseline_control(
        "C41-OVR-1", name="표준명", owner_name="표준담당", is_key_control=True, frequency="A",
    )
    resp = client.patch(f"/api/rcm/controls/{bid}", json={
        "name": "회사 변경명", "is_key_control": False,  # 이 둘만 변경
    }, headers=h)
    assert resp.status_code == 200
    body = resp.json()
    assert body["source"] == "baseline" and body["is_overridden"] is True
    assert body["name"] == "회사 변경명"
    assert body["is_key_control"] is False
    assert body["owner_name"] == "표준담당"  # 미전송 → baseline
    assert body["frequency"] == "A"          # 미전송 → baseline

    inst = _instance_for(bid)
    assert inst.action == "override"
    assert inst.name == "회사 변경명"
    assert inst.is_key_control is False   # False 는 유효 override (NULL 아님)
    assert inst.owner_name is None        # 안 바뀐 필드 = NULL(baseline 따름)
    assert inst.frequency is None

    # baseline 원본 불변
    db = TestingSessionLocal()
    try:
        assert db.query(BaselineControl).filter(BaselineControl.id == UUID(bid)).one().name == "표준명"
    finally:
        db.close()


# ── PATCH: baseline 과 같게 되돌리면 → adopt 전환 ────────────

def test_patch_revert_to_baseline_becomes_adopt(client: TestClient) -> None:
    h = _headers(client)
    bid = _seed_baseline_control("C41-REV-1", name="표준명", is_key_control=True)
    client.patch(f"/api/rcm/controls/{bid}", json={"name": "회사명", "is_key_control": False}, headers=h)
    assert _instance_for(bid).action == "override"

    # 전부 baseline 값으로 되돌림
    resp = client.patch(f"/api/rcm/controls/{bid}", json={"name": "표준명", "is_key_control": True}, headers=h)
    assert resp.status_code == 200
    assert resp.json()["is_overridden"] is False  # adopt
    inst = _instance_for(bid)
    assert inst.action == "adopt"          # instance 는 남김(검토 흔적)
    assert inst.name is None and inst.is_key_control is None


# ── PATCH(add) → instance 직접 수정 ─────────────────────────

def test_patch_add_updates_instance_directly(client: TestClient) -> None:
    h = _headers(client)
    rid = _seed_baseline_risk("PADD")
    cid = client.post("/api/rcm/controls", json={
        "code": "C41-PADD-1", "name": "회사통제", "risk_id": rid, "frequency": "M",
    }, headers=h).json()["id"]

    resp = client.patch(f"/api/rcm/controls/{cid}", json={"frequency": "Q", "auto_manual": "A"}, headers=h)
    assert resp.status_code == 200
    assert resp.json()["frequency"] == "Q"
    assert resp.json()["auto_manual"] == "A"
    assert resp.json()["source"] == "tenant"


# ── DELETE(baseline) → exclude, baseline 불변 ───────────────

def test_delete_baseline_creates_exclude(client: TestClient) -> None:
    h = _headers(client)
    before = _baseline_count()
    bid = _seed_baseline_control("C41-DEL-1", name="삭제대상")
    assert _baseline_count() == before + 1

    resp = client.delete(f"/api/rcm/controls/{bid}", headers=h)
    assert resp.status_code == 204

    # resolve 에서 사라짐
    assert client.get(f"/api/rcm/controls/{bid}", headers=h).status_code == 404
    # exclude instance 생성, baseline row 는 그대로
    assert _instance_for(bid).action == "exclude"
    assert _baseline_count() == before + 1  # 물리·soft 삭제 없음


# ── DELETE(add) → soft delete ──────────────────────────────

def test_delete_add_soft_deletes(client: TestClient) -> None:
    h = _headers(client)
    rid = _seed_baseline_risk("DADD")
    cid = client.post("/api/rcm/controls", json={
        "code": "C41-DADD-1", "name": "회사통제", "risk_id": rid, "frequency": "M",
    }, headers=h).json()["id"]

    assert client.delete(f"/api/rcm/controls/{cid}", headers=h).status_code == 204
    assert client.get(f"/api/rcm/controls/{cid}", headers=h).status_code == 404

    db = TestingSessionLocal()
    tok = set_active_tenant(DEFAULT_TENANT_ID)
    try:
        inst = db.query(ControlInstance).filter(ControlInstance.id == UUID(cid)).one()
        assert inst.is_deleted is True
    finally:
        reset_active_tenant(tok)
        db.close()


# ── falsy 유효값 (False/"") override ────────────────────────

def test_patch_falsy_values_are_valid_override(client: TestClient) -> None:
    h = _headers(client)
    bid = _seed_baseline_control(
        "C41-FAL-1", name="표준명", description="표준설명",
        is_key_control=True, activity_approval=True,
    )
    resp = client.patch(f"/api/rcm/controls/{bid}", json={
        "is_key_control": False, "activity_approval": False, "description": "",
    }, headers=h)
    assert resp.status_code == 200
    body = resp.json()
    assert body["is_key_control"] is False       # False 반영 (baseline True 와 다름)
    assert body["activity_approval"] is False
    assert body["description"] == ""             # "" 반영 (baseline "표준설명" 과 다름)

    inst = _instance_for(bid)
    assert inst.is_key_control is False           # NULL 아님
    assert inst.activity_approval is False
    assert inst.description == ""
