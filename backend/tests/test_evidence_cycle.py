"""증빙 통제×회차 부착·경로·권한·정책 (3-3, ADR-0032 §2.1~2.3·§2.5~2.7).

§2.4(삭제 시 파일 보존)는 `test_evidence_retention.py` 가 담당한다 — 여기서는
재확인만 한다(`test_delete_still_keeps_file`).

MinIO 는 테스트 환경에 없으므로 저장소 호출을 메모리 대역으로 바꾼다.
**경로 문자열은 대역에서도 그대로 만들어지므로 §5-14(경로에 tenant_id 포함)는
여기서 실증된다.**
"""
import io
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.api import evidence as evidence_api
from app.core.security import hash_password
from app.core.tenant_context import DEFAULT_TENANT_ID, reset_active_tenant, set_active_tenant
from app.models.assessment import CYCLE_CLOSED, AssessmentCycle, CycleTarget
from app.models.evidence import EvidenceFile
from app.models.rcm_baseline import (
    BaselineControl,
    BaselineProcess,
    BaselineRisk,
    BaselineSubProcess,
)
from app.models.role_assignment import RoleAssignment
from app.models.tenant import Tenant, UserTenantAccess
from app.models.user import User
from app.models.user_mgmt import UserRole
from tests.conftest import TestingSessionLocal


@pytest.fixture
def storage(monkeypatch):
    store: dict[str, bytes] = {}

    def _upload(object_key: str, data_bytes: bytes, content_type: str) -> None:
        store[object_key] = data_bytes

    class _Resp:
        def __init__(self, data: bytes):
            self._buf = io.BytesIO(data)

        def stream(self, chunk_size: int = 8192):
            while True:
                chunk = self._buf.read(chunk_size)
                if not chunk:
                    return
                yield chunk

        def close(self):
            pass

        def release_conn(self):
            pass

    monkeypatch.setattr(evidence_api, "upload_object", _upload)
    monkeypatch.setattr(evidence_api, "get_object_stream", lambda k: _Resp(store[k]))
    return store


def _login(client: TestClient, email="admin@acme.example", pw="admin123") -> dict:
    resp = client.post("/api/auth/login", data={"username": email, "password": pw})
    assert resp.status_code == 200, resp.text
    return {"Authorization": "Bearer " + resp.json()["access_token"]}


def _user(db, email: str, name: str, roles: tuple[str, ...] = ()) -> UUID:
    u = db.query(User).filter(User.email == email).first()
    if u is None:
        u = User(email=email, hashed_password=hash_password("pw123456"),
                 display_name=name, role="user", is_active=True)
        db.add(u)
        db.commit()
    if db.query(UserTenantAccess).filter(
        UserTenantAccess.user_id == u.id, UserTenantAccess.tenant_id == DEFAULT_TENANT_ID,
    ).first() is None:
        db.add(UserTenantAccess(user_id=u.id, tenant_id=DEFAULT_TENANT_ID, role="user"))
    for r in roles:
        if db.query(UserRole).filter(UserRole.user_id == u.id,
                                     UserRole.role_name == r).first() is None:
            db.add(UserRole(user_id=u.id, role_name=r))
    db.commit()
    return u.id


def _control(db, suffix: str) -> UUID:
    p = BaselineProcess(code=f"EV{suffix}-P", name="P")
    db.add(p)
    db.flush()
    sp = BaselineSubProcess(code=f"EV{suffix}-SP", name="SP", process_id=p.id)
    db.add(sp)
    db.flush()
    r = BaselineRisk(code=f"EV{suffix}-R", description="R", assessment_level="LR",
                     sub_process_id=sp.id)
    db.add(r)
    db.flush()
    c = BaselineControl(code=f"EV{suffix}-C", name="C", risk_id=r.id)
    db.add(c)
    db.commit()
    return c.id


def _cycle(db, suffix: str, control_id: UUID, status: str = "open") -> UUID:
    from datetime import date

    cy = AssessmentCycle(kind="operation", frequency="annual", name=f"증빙회차-{suffix}",
                         period_start=date(2026, 1, 1), period_end=date(2026, 12, 31),
                         status=status)
    db.add(cy)
    db.flush()
    db.add(CycleTarget(cycle_id=cy.id, control_id=control_id, control_code=f"EV{suffix}-C"))
    db.commit()
    return cy.id


def _ctx():
    db = TestingSessionLocal()
    return db, set_active_tenant(DEFAULT_TENANT_ID)


def _upload(client, h, cycle_id, control_id, name="증빙.pdf", body=b"%PDF-1.4 x"):
    return client.post("/api/evidence/files", headers=h,
                       data={"cycle_id": str(cycle_id), "control_id": str(control_id)},
                       files={"file": (name, body, "application/pdf")})


# ── §5-1·2 통제×회차 부착 ─────────────────────────────────

def test_multiple_evidence_per_control_and_cycle(client: TestClient, storage) -> None:
    """§5-1 — 같은 통제×회차에 여러 개 업로드 가능하고 업로더가 각각 기록된다."""
    db, tok = _ctx()
    try:
        owner = _user(db, "ev-owner1@acme.example", "책임자1")
        ctrl = _control(db, "M1")
        cyc = _cycle(db, "M1", ctrl)
        db.add(RoleAssignment(scope="control", target_id=ctrl,
                              role_name="control_owner", user_id=owner))
        db.commit()
    finally:
        reset_active_tenant(tok)
        db.close()

    oh = _login(client, "ev-owner1@acme.example", "pw123456")
    a = _upload(client, oh, cyc, ctrl, "첫번째.pdf")
    b = _upload(client, oh, cyc, ctrl, "두번째.pdf")
    assert a.status_code == 201, a.text
    assert b.status_code == 201, b.text
    assert a.json()["uploaded_by_id"] == str(owner)
    assert a.json()["id"] != b.json()["id"]
    assert a.json()["cycle_id"] == str(cyc) and a.json()["control_id"] == str(ctrl)


def test_same_control_different_cycles_are_separate(client: TestClient, storage) -> None:
    """§5-2 — 같은 통제라도 회차가 다르면 별개 증빙이다."""
    db, tok = _ctx()
    try:
        owner = _user(db, "ev-owner2@acme.example", "책임자2")
        ctrl = _control(db, "S1")
        c1 = _cycle(db, "S1a", ctrl)
        c2 = _cycle(db, "S1b", ctrl)
        db.add(RoleAssignment(scope="control", target_id=ctrl,
                              role_name="control_owner", user_id=owner))
        db.commit()
    finally:
        reset_active_tenant(tok)
        db.close()

    oh = _login(client, "ev-owner2@acme.example", "pw123456")
    e1 = _upload(client, oh, c1, ctrl, "1회차.pdf").json()
    e2 = _upload(client, oh, c2, ctrl, "2회차.pdf").json()
    assert e1["cycle_id"] != e2["cycle_id"]
    assert e1["minio_key"] != e2["minio_key"]       # 경로도 회차별로 갈린다


# ── §5-14·§2.2·§2.3 경로 ──────────────────────────────────

def test_minio_key_contains_tenant_and_is_internal_id(client: TestClient, storage) -> None:
    """§5-14 — 경로에 `tenant_id` 가 포함되고, **파일명이 경로에 들어가지 않는다**(§2.3).

    한글 파일명·중복 이름·경로 조작 시도가 내부 식별자 저장으로 한 번에 해결된다.
    """
    db, tok = _ctx()
    try:
        owner = _user(db, "ev-path@acme.example", "경로검증")
        ctrl = _control(db, "P1")
        cyc = _cycle(db, "P1", ctrl)
        db.add(RoleAssignment(scope="control", target_id=ctrl,
                              role_name="control_owner", user_id=owner))
        db.commit()
    finally:
        reset_active_tenant(tok)
        db.close()

    oh = _login(client, "ev-path@acme.example", "pw123456")
    body = _upload(client, oh, cyc, ctrl, "../../탈출시도.pdf").json()
    key = body["minio_key"]

    assert key.startswith(f"{DEFAULT_TENANT_ID}/")
    assert key == f"{DEFAULT_TENANT_ID}/cycles/{cyc}/controls/{ctrl}/{body['id']}"
    assert "탈출시도" not in key and ".." not in key      # 파일명이 경로에 없다
    assert body["filename"] == "../../탈출시도.pdf"       # 원본명은 DB 에 그대로


def test_path_builder_is_the_only_assembler() -> None:
    """경로를 만드는 곳이 하나뿐이다 (§2.2).

    경로 분리는 DB 복합 FK 같은 구조적 보장이 없다 — 문자열을 여기저기서 이어붙이면
    한 곳만 틀려도 다른 테넌트 경로에 쓰게 된다.
    """
    import inspect

    from app import minio_client
    from app.api import evidence

    src = inspect.getsource(evidence)
    assert "build_evidence_key(" in src
    assert "/cycles/" not in src        # API 모듈이 경로를 조립하지 않는다
    assert "/cycles/" in inspect.getsource(minio_client.build_evidence_key)


def test_path_builder_requires_tenant_context() -> None:
    """`tenant_id` 를 호출자가 넘기지 않는다 — 컨텍스트가 없으면 만들지 않는다."""
    from app.minio_client import build_evidence_key

    with pytest.raises(RuntimeError, match="활성 tenant"):
        build_evidence_key(uuid4(), uuid4(), uuid4())


# ── 조건 3: cycle_id 필수 ─────────────────────────────────

def test_upload_requires_cycle_and_control(client: TestClient, storage) -> None:
    """신규 업로드는 `cycle_id`·`control_id` 가 필수다 — 핸들러가 막는다.

    컬럼은 nullable 이다(레거시 4건 때문). "레거시는 NULL 을 허용하되 신규는 만들지
    않는다"를 애플리케이션이 담당한다.
    """
    h = _login(client)
    resp = client.post("/api/evidence/files", headers=h,
                       files={"file": ("무회차.pdf", b"%PDF-1.4", "application/pdf")})
    assert resp.status_code == 422, resp.text        # Form 필수 누락


def test_upload_rejects_unknown_cycle(client: TestClient, storage) -> None:
    """존재하지 않는 회차면 404 — 회차 없는 증빙이 신규로 생기지 않는다."""
    db, tok = _ctx()
    try:
        ctrl = _control(db, "U1")
    finally:
        reset_active_tenant(tok)
        db.close()
    h = _login(client)
    resp = _upload(client, h, uuid4(), ctrl)
    assert resp.status_code == 404, resp.text


# ── §5-7·8·9·11 권한 ──────────────────────────────────────

def test_owner_cannot_upload_to_closed_cycle(client: TestClient, storage) -> None:
    """§5-7 — 마감된 회차에 통제책임자가 업로드하면 거부된다."""
    db, tok = _ctx()
    try:
        owner = _user(db, "ev-closed@acme.example", "마감책임자")
        ctrl = _control(db, "C1")
        cyc = _cycle(db, "C1", ctrl, status=CYCLE_CLOSED)
        db.add(RoleAssignment(scope="control", target_id=ctrl,
                              role_name="control_owner", user_id=owner))
        db.commit()
    finally:
        reset_active_tenant(tok)
        db.close()

    oh = _login(client, "ev-closed@acme.example", "pw123456")
    resp = _upload(client, oh, cyc, ctrl)
    assert resp.status_code == 403, resp.text
    assert "내부회계관리자만" in resp.json()["detail"]


def test_icfr_manager_can_upload_to_closed_cycle(client: TestClient, storage) -> None:
    """§5-8 — 마감된 회차에도 `icfr_manager` 는 업로드할 수 있고 이력에 남는다.

    정정이 필요한 경우가 실재하며, 누가 했는지는 업로더 계정으로 남는다.
    """
    db, tok = _ctx()
    try:
        mgr = _user(db, "ev-mgr@acme.example", "내부회계관리자", ("icfr_manager",))
        ctrl = _control(db, "C2")
        cyc = _cycle(db, "C2", ctrl, status=CYCLE_CLOSED)
    finally:
        reset_active_tenant(tok)
        db.close()

    mh = _login(client, "ev-mgr@acme.example", "pw123456")
    resp = _upload(client, mh, cyc, ctrl, "정정증빙.pdf")
    assert resp.status_code == 201, resp.text

    hist = client.get(f"/api/evidence/files/{resp.json()['id']}/history", headers=mh).json()
    assert hist["uploaded_by_id"] == str(mgr)
    assert hist["uploaded_by_name"] == "내부회계관리자"


def test_policy_toggle_blocks_owner_upload(client: TestClient, storage) -> None:
    """§5-9 — 정책 토글이 금지면 진행 중 회차에서도 통제책임자 업로드가 거부된다."""
    db, tok = _ctx()
    try:
        owner = _user(db, "ev-pol@acme.example", "정책책임자")
        admin = db.query(User).filter(User.email == "admin@acme.example").one()
        if db.query(UserRole).filter(UserRole.user_id == admin.id,
                                     UserRole.role_name == "icfr_manager").first() is None:
            db.add(UserRole(user_id=admin.id, role_name="icfr_manager"))
        ctrl = _control(db, "PL1")
        cyc = _cycle(db, "PL1", ctrl)
        db.add(RoleAssignment(scope="control", target_id=ctrl,
                              role_name="control_owner", user_id=owner))
        db.commit()
    finally:
        reset_active_tenant(tok)
        db.close()

    h = _login(client)
    assert client.put("/api/org/policies", headers=h, json={
        "policy_key": "evidence_edit_enabled", "policy_value": "false"}).status_code == 200
    try:
        oh = _login(client, "ev-pol@acme.example", "pw123456")
        resp = _upload(client, oh, cyc, ctrl)
        assert resp.status_code == 403, resp.text
        assert "비활성화" in resp.json()["detail"]
    finally:
        client.put("/api/org/policies", headers=h, json={
            "policy_key": "evidence_edit_enabled", "policy_value": "true"})


def test_owner_of_other_control_cannot_upload(client: TestClient, storage) -> None:
    """§5-11 — 통제 A 의 책임자가 통제 B 의 증빙을 올릴 수 없다 (통제 단위 권한)."""
    db, tok = _ctx()
    try:
        owner_a = _user(db, "ev-a@acme.example", "A책임자")
        ctrl_a = _control(db, "XA")
        ctrl_b = _control(db, "XB")
        cyc = _cycle(db, "XB", ctrl_b)
        db.add(RoleAssignment(scope="control", target_id=ctrl_a,
                              role_name="control_owner", user_id=owner_a))
        db.commit()
    finally:
        reset_active_tenant(tok)
        db.close()

    ah = _login(client, "ev-a@acme.example", "pw123456")
    resp = _upload(client, ah, cyc, ctrl_b)
    assert resp.status_code == 403, resp.text
    assert "통제책임자만" in resp.json()["detail"]


# ── §5-10 external_auditor ────────────────────────────────

def test_external_auditor_cannot_upload_or_delete(client: TestClient, storage) -> None:
    """§5-10 — `external_auditor` 는 업로드·삭제 불가, 조회는 가능."""
    db, tok = _ctx()
    try:
        _user(db, "ev-ext@acme.example", "외부감사인", ("external_auditor",))
        ctrl = _control(db, "EX1")
        cyc = _cycle(db, "EX1", ctrl)
    finally:
        reset_active_tenant(tok)
        db.close()

    eh = _login(client, "ev-ext@acme.example", "pw123456")
    up = _upload(client, eh, cyc, ctrl)
    assert up.status_code == 403 and "외부감사인" in up.json()["detail"]

    h = _login(client)
    fid = _upload(client, h, cyc, ctrl, "감사인삭제대상.pdf").json()["id"]
    dele = client.delete(f"/api/evidence/files/{fid}", headers=eh)
    assert dele.status_code == 403
    assert client.get("/api/evidence/files", headers=eh).status_code == 200


# ── §5-12 보존기간 ────────────────────────────────────────

def test_retention_below_five_years_rejected(client: TestClient) -> None:
    """§5-12 — 보존기간 5년 미만은 거부. 0 은 영구 보존이라 허용된다.

    근거: 내부회계관리제도 업무지침 — 회계정보 및 관련 문서 5년 보관(§2.9).
    """
    db, tok = _ctx()
    try:
        admin = db.query(User).filter(User.email == "admin@acme.example").one()
        if db.query(UserRole).filter(UserRole.user_id == admin.id,
                                     UserRole.role_name == "icfr_manager").first() is None:
            db.add(UserRole(user_id=admin.id, role_name="icfr_manager"))
            db.commit()
    finally:
        reset_active_tenant(tok)
        db.close()

    h = _login(client)
    bad = client.put("/api/org/policies", headers=h, json={
        "policy_key": "evidence_retention_years", "policy_value": "3"})
    assert bad.status_code == 409, bad.text
    assert "최소 5년" in bad.json()["detail"]

    assert client.put("/api/org/policies", headers=h, json={
        "policy_key": "evidence_retention_years", "policy_value": "5"}).status_code == 200
    assert client.put("/api/org/policies", headers=h, json={
        "policy_key": "evidence_retention_years", "policy_value": "0"}).status_code == 200

    nan = client.put("/api/org/policies", headers=h, json={
        "policy_key": "evidence_retention_years", "policy_value": "영구"})
    assert nan.status_code == 422


# ── §5-13 테넌트 격리 ─────────────────────────────────────

def test_other_tenant_evidence_not_accessible(client: TestClient, storage) -> None:
    """§5-13 — 다른 테넌트의 증빙에 접근할 수 없다. **DB 조회 단계에서 걸러진다.**

    경로 격리는 DB 같은 구조적 보장이 없다 — "경로를 조작해도 못 읽는다"가 아니라
    "DB 조회에서 걸러진다"를 검증한다. 다운로드도 경로를 파라미터로 받지 않고
    레코드를 조회해 그 `minio_key` 를 쓴다.
    """
    db, tok = _ctx()
    try:
        ctrl = _control(db, "T1")
        cyc = _cycle(db, "T1", ctrl)
    finally:
        reset_active_tenant(tok)
        db.close()

    h = _login(client)
    fid = _upload(client, h, cyc, ctrl, "A사증빙.pdf").json()["id"]

    db = TestingSessionLocal()
    try:
        other = db.query(Tenant).filter(Tenant.code == "TENANT_EV_B").first()
        if other is None:
            other = Tenant(name="회사B-증빙", code="TENANT_EV_B", is_active=True)
            db.add(other)
            db.commit()
        tok2 = set_active_tenant(other.id)
        try:
            assert db.query(EvidenceFile).filter(
                EvidenceFile.id == UUID(fid)).first() is None
        finally:
            reset_active_tenant(tok2)
    finally:
        db.close()


# ── §2.4 재확인 ───────────────────────────────────────────

def test_delete_still_keeps_file(client: TestClient, storage) -> None:
    """§5-5·6 재확인 — 통제×회차 부착 후에도 삭제 시 파일이 남는다."""
    db, tok = _ctx()
    try:
        mgr = _user(db, "ev-del@acme.example", "삭제관리자", ("icfr_manager",))
        ctrl = _control(db, "D1")
        cyc = _cycle(db, "D1", ctrl)
    finally:
        reset_active_tenant(tok)
        db.close()
    assert mgr is not None

    mh = _login(client, "ev-del@acme.example", "pw123456")
    created = _upload(client, mh, cyc, ctrl, "삭제검증.pdf").json()
    key = created["minio_key"]
    assert key in storage

    assert client.delete(f"/api/evidence/files/{created['id']}",
                         headers=mh, params={"reason": "중복 등록"}).status_code == 204
    assert key in storage                                     # 파일이 남는다
    hist = client.get(f"/api/evidence/files/{created['id']}/history", headers=mh).json()
    assert hist["is_deleted"] is True and hist["delete_reason"] == "중복 등록"
