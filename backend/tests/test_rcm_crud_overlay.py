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


# ── 2-A-4-2: 다건(bulk) — 단건과 같은 분기 ────────────────────

def _instance_by_id(instance_id: str) -> ControlInstance | None:
    db = TestingSessionLocal()
    tok = set_active_tenant(DEFAULT_TENANT_ID)
    try:
        return db.query(ControlInstance).filter(ControlInstance.id == UUID(instance_id)).first()
    finally:
        reset_active_tenant(tok)
        db.close()


def _add_control(client: TestClient, h: dict, suffix: str) -> str:
    """회사 add 통제 1건 생성 후 id 반환."""
    rid = _seed_baseline_risk(suffix)
    resp = client.post("/api/rcm/controls", json={
        "code": f"C42-ADD-{suffix}", "name": f"회사통제{suffix}", "risk_id": rid, "frequency": "M",
    }, headers=h)
    assert resp.status_code == 201
    return resp.json()["id"]


def _search_codes(client: TestClient, h: dict) -> list[str]:
    resp = client.get("/api/rcm/controls/search", params={"limit": 500}, headers=h)
    return [c["code"] for c in resp.json()["items"]]


def test_bulk_delete_uses_same_branching_as_single(client: TestClient) -> None:
    """baseline 유래 → exclude instance, 회사 add → soft delete, 미해당 id → skipped."""
    h = _headers(client)
    before = _baseline_count()
    bid = _seed_baseline_control("C42-BDEL-1", name="표준통제")
    add_id = _add_control(client, h, "BDEL")
    missing = "00000000-0000-0000-0000-0000000042de"

    resp = client.post("/api/rcm/controls/bulk-delete", json={
        "control_ids": [bid, add_id, missing],
    }, headers=h)
    assert resp.status_code == 200
    body = resp.json()
    assert body["deleted_count"] == 2
    assert body["skipped_ids"] == [missing]

    # baseline 유래 = exclude instance (원본은 그대로)
    inst = _instance_for(bid)
    assert inst is not None and inst.action == "exclude"

    # 회사 add = soft delete
    assert _instance_by_id(add_id).is_deleted is True

    # 둘 다 목록에서 사라진다
    codes = _search_codes(client, h)
    assert "C42-BDEL-1" not in codes
    assert "C42-ADD-BDEL" not in codes

    # baseline 원본 불변 — 행 수도 내용도 (이 테스트가 시딩한 1건만 증가)
    assert _baseline_count() == before + 1
    db = TestingSessionLocal()
    try:
        bc = db.query(BaselineControl).filter(BaselineControl.id == UUID(bid)).first()
        assert bc is not None and bc.name == "표준통제" and bc.is_deleted is False
    finally:
        db.close()


def test_bulk_update_baseline_creates_override_diff(client: TestClient) -> None:
    """baseline 유래 → override, 전송 필드만 저장(나머지는 baseline 따름)."""
    h = _headers(client)
    b1 = _seed_baseline_control("C42-BUPD-1", name="표준1", owner_name="표준담당", frequency="A")
    b2 = _seed_baseline_control("C42-BUPD-2", name="표준2", owner_name="표준담당", frequency="A")

    resp = client.post("/api/rcm/controls/bulk-update", json={
        "control_ids": [b1, b2], "updates": {"frequency": "Q"},
    }, headers=h)
    assert resp.status_code == 200
    assert resp.json()["updated_count"] == 2
    assert resp.json()["skipped_ids"] == []

    for bid in (b1, b2):
        inst = _instance_for(bid)
        assert inst.action == "override"
        assert inst.frequency == "Q"
        assert inst.name is None        # 미전송 → NULL(baseline 따름)
        assert inst.owner_name is None

    # baseline 원본 불변
    db = TestingSessionLocal()
    try:
        bc = db.query(BaselineControl).filter(BaselineControl.id == UUID(b1)).first()
        assert bc.frequency == "A" and bc.name == "표준1"
    finally:
        db.close()


def test_bulk_update_add_instance_is_edited_directly(client: TestClient) -> None:
    """회사 add → instance 직접 수정 (diff 불필요)."""
    h = _headers(client)
    add_id = _add_control(client, h, "BUPD")

    resp = client.post("/api/rcm/controls/bulk-update", json={
        "control_ids": [add_id], "updates": {"frequency": "D", "owner_name": "회사담당"},
    }, headers=h)
    assert resp.status_code == 200
    assert resp.json()["updated_count"] == 1

    inst = _instance_by_id(add_id)
    assert inst.action == "add"
    assert inst.frequency == "D" and inst.owner_name == "회사담당"


def test_bulk_update_falsy_values_are_stored(client: TestClient) -> None:
    """False/"" 는 유효 값 — exclude_unset 통일 전(exclude_none)에는 저장되지 않았다.

    ControlUpdate 에 정수 필드가 없어 0 은 이 스키마로 표현 불가(False 가 동일 경로).
    """
    h = _headers(client)
    bid = _seed_baseline_control(
        "C42-BFAL-1", name="표준명", description="표준설명",
        is_key_control=True, activity_approval=True,
    )
    resp = client.post("/api/rcm/controls/bulk-update", json={
        "control_ids": [bid],
        "updates": {"is_key_control": False, "activity_approval": False, "description": ""},
    }, headers=h)
    assert resp.status_code == 200
    assert resp.json()["updated_count"] == 1

    inst = _instance_for(bid)
    assert inst.is_key_control is False      # NULL 로 떨어지지 않음
    assert inst.activity_approval is False
    assert inst.description == ""

    resolved = client.get(f"/api/rcm/controls/{bid}", headers=h).json()
    assert resolved["is_key_control"] is False
    assert resolved["activity_approval"] is False
    assert resolved["description"] == ""


def test_bulk_update_back_to_baseline_reverts_to_adopt(client: TestClient) -> None:
    """전 override 필드가 baseline 과 같아지면 adopt 로 되돌린다(instance 는 남김)."""
    h = _headers(client)
    bid = _seed_baseline_control("C42-BREV-1", name="표준명", frequency="A")

    client.post("/api/rcm/controls/bulk-update", json={
        "control_ids": [bid], "updates": {"frequency": "Q"},
    }, headers=h)
    assert _instance_for(bid).action == "override"

    client.post("/api/rcm/controls/bulk-update", json={
        "control_ids": [bid], "updates": {"frequency": "A"},  # baseline 과 동일
    }, headers=h)
    inst = _instance_for(bid)
    assert inst is not None            # instance 자체는 남는다 (검토 흔적)
    assert inst.action == "adopt"      # 되돌림
    assert inst.frequency is None      # 값도 정리


def test_bulk_update_skips_unknown_ids(client: TestClient) -> None:
    """미해당 id 는 skipped_ids 로 나오고 전체를 실패시키지 않는다."""
    h = _headers(client)
    bid = _seed_baseline_control("C42-BSKIP-1", name="표준명", frequency="A")
    missing = "00000000-0000-0000-0000-0000000042bd"

    resp = client.post("/api/rcm/controls/bulk-update", json={
        "control_ids": [bid, missing], "updates": {"frequency": "W"},
    }, headers=h)
    assert resp.status_code == 200
    assert resp.json()["updated_count"] == 1
    assert resp.json()["skipped_ids"] == [missing]


# ── 2-A-4-2: GET /controls 목록 전환 ─────────────────────────

def test_list_controls_uses_resolver_with_envelope(client: TestClient) -> None:
    """목록이 resolver 기반이고 envelope 를 포함하며 search 와 id 가 일치한다."""
    h = _headers(client)
    bid = _seed_baseline_control("C42-LIST-1", name="목록표준")
    add_id = _add_control(client, h, "LIST")

    resp = client.get("/api/rcm/controls", params={"limit": 500}, headers=h)
    assert resp.status_code == 200
    items = {c["code"]: c for c in resp.json()["items"]}

    assert "C42-LIST-1" in items
    assert items["C42-LIST-1"]["id"] == bid          # 정체성 id = baseline id
    assert items["C42-LIST-1"]["source"] == "baseline"
    assert items["C42-LIST-1"]["is_overridden"] is False

    assert "C42-ADD-LIST" in items
    assert items["C42-ADD-LIST"]["id"] == add_id     # add 는 instance id
    assert items["C42-ADD-LIST"]["source"] == "tenant"
    assert items["C42-ADD-LIST"]["baseline_id"] is None

    # search 와 id 체계 일치
    s = client.get("/api/rcm/controls/search", params={"limit": 500}, headers=h)
    s_items = {c["code"]: c for c in s.json()["items"]}
    for code in ("C42-LIST-1", "C42-ADD-LIST"):
        assert items[code]["id"] == s_items[code]["id"]


def test_list_controls_excludes_deleted(client: TestClient) -> None:
    """exclude/soft delete 된 통제는 목록에서 빠진다."""
    h = _headers(client)
    bid = _seed_baseline_control("C42-LDEL-1", name="목록삭제")

    def _codes() -> list[str]:
        return [c["code"] for c in
                client.get("/api/rcm/controls", params={"limit": 500}, headers=h).json()["items"]]

    assert "C42-LDEL-1" in _codes()
    client.delete(f"/api/rcm/controls/{bid}", headers=h)
    assert "C42-LDEL-1" not in _codes()
