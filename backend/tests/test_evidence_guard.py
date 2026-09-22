"""증빙 쓰기 권한 구멍 수정 (13.9-48).

막은 경로 4개:
- `POST/DELETE /api/evidence/links` — 로그인만 확인해 **외부감사인이 증빙 연결을 만들고 지울 수 있었다**
- `PATCH /api/evidence/files/{id}` — 로그인만 확인했고 **`minio_key` 까지 바꿀 수 있었다**
  (증빙 레코드가 다른 파일을 가리키게 만드는 경로)
- `DELETE /api/evidence/files/{id}` 의 레거시(회차 없음) 증빙 — `require_write` 만 적용됐다
"""
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.tenant_context import DEFAULT_TENANT_ID, reset_active_tenant
from app.models.assessment import CYCLE_CLOSED
from app.models.evidence import EvidenceFile, EvidenceLink
from app.models.role_assignment import RoleAssignment
from app.models.user import User
from tests.conftest import TestingSessionLocal
from tests.test_evidence_cycle import (  # noqa: F401
    _control,
    _ctx,
    _cycle,
    _login,
    _upload,
    _user,
    storage,
)

# MinIO 대역 — 이 파일의 모든 테스트에 건다
pytestmark = pytest.mark.usefixtures("storage")

PW = "pw123456"


def _setup(suffix: str, status: str = "open") -> tuple[UUID, UUID]:
    """관리자·외부감사인·무역할·통제책임자 계정 + 통제 1 + 회차 1."""
    db, tok = _ctx()
    try:
        _user(db, "eg-mgr@acme.example", "관리자", ("icfr_manager",))
        _user(db, "eg-ext@acme.example", "외부감사인", ("external_auditor",))
        _user(db, "eg-plain@acme.example", "무역할")
        owner = _user(db, f"eg-owner-{suffix}@acme.example", "책임자")
        ctrl = _control(db, f"G{suffix}")
        cyc = _cycle(db, f"G{suffix}", ctrl, status=status)
        db.add(RoleAssignment(scope="control", target_id=ctrl, role_name="control_owner", user_id=owner))
        db.commit()
    finally:
        reset_active_tenant(tok)
        db.close()
    return ctrl, cyc


def _link_body(fid: str, ctrl: UUID, kind: str = "control") -> dict:
    return {"file_id": fid, "linked_entity_type": kind, "linked_entity_id": str(ctrl)}


# ── 증빙 연결: icfr_manager 전용 ───────────────────────────

def test_only_icfr_manager_can_create_or_delete_link(client: TestClient) -> None:
    """외부감사인·무역할·**그 통제의 통제책임자**까지 403. 쓰는 곳이 없는 경로라 관리자 전용이다."""
    ctrl, cyc = _setup("L1")
    mh = _login(client, "eg-mgr@acme.example", PW)
    fid = _upload(client, mh, cyc, ctrl).json()["id"]
    link = client.post("/api/evidence/links", headers=mh, json=_link_body(fid, ctrl))
    assert link.status_code == 201, link.text
    for email in ("eg-ext@acme.example", "eg-plain@acme.example", "eg-owner-L1@acme.example"):
        h = _login(client, email, PW)
        assert client.post("/api/evidence/links", headers=h, json=_link_body(fid, ctrl)).status_code == 403
        assert client.delete(f"/api/evidence/links/{link.json()['id']}", headers=h).status_code == 403
        assert client.get("/api/evidence/links", headers=h).status_code == 200   # 조회는 인증만


def test_link_validation(client: TestClient) -> None:
    """허용 목록 밖 종류 422 · 없는 통제 404 · 없는(다른 회사 포함) 파일 404 · 삭제된 파일 404."""
    ctrl, cyc = _setup("L2")
    mh = _login(client, "eg-mgr@acme.example", PW)
    fid = _upload(client, mh, cyc, ctrl).json()["id"]
    r = client.post("/api/evidence/links", headers=mh, json=_link_body(fid, ctrl, "scoping"))
    assert r.status_code == 422 and "허용" in r.json()["detail"]
    assert client.post("/api/evidence/links", headers=mh,
                       json=_link_body(fid, uuid4())).status_code == 404
    assert client.post("/api/evidence/links", headers=mh,
                       json=_link_body(str(uuid4()), ctrl)).status_code == 404
    gone = _upload(client, mh, cyc, ctrl, "지울것.pdf").json()["id"]
    client.delete(f"/api/evidence/files/{gone}", headers=mh)
    assert client.post("/api/evidence/links", headers=mh, json=_link_body(gone, ctrl)).status_code == 404


def test_link_delete_records_who_and_when(client: TestClient) -> None:
    """소프트 삭제 + `deleted_by`(사용자 id)·`deleted_at`. 생성도 `created_by` 를 남긴다."""
    ctrl, cyc = _setup("L3")
    mh = _login(client, "eg-mgr@acme.example", PW)
    fid = _upload(client, mh, cyc, ctrl).json()["id"]
    lid = client.post("/api/evidence/links", headers=mh, json=_link_body(fid, ctrl)).json()["id"]
    assert client.delete(f"/api/evidence/links/{lid}", headers=mh).status_code == 204
    listed = client.get("/api/evidence/links", headers=mh, params={"file_id": fid}).json()
    assert listed["total"] == 0
    db = TestingSessionLocal()
    try:
        mgr = db.query(User).filter(User.email == "eg-mgr@acme.example").one()
        row = db.query(EvidenceLink).filter(EvidenceLink.id == UUID(lid)).one()   # 행은 남는다
        assert row.is_deleted is True
        assert row.created_by == str(mgr.id) and row.deleted_by == str(mgr.id)
        assert row.deleted_at is not None
    finally:
        db.close()


# ── 파일 수정: minio_key 불가 + 업로드와 같은 판정 ─────────

def test_minio_key_cannot_be_changed_by_anyone(client: TestClient) -> None:
    ctrl, cyc = _setup("F1")
    mh = _login(client, "eg-mgr@acme.example", PW)
    f = _upload(client, mh, cyc, ctrl).json()
    r = client.patch(f"/api/evidence/files/{f['id']}", headers=mh, json={"minio_key": "tenants/x/other.pdf"})
    assert r.status_code == 422
    assert client.get(f"/api/evidence/files/{f['id']}", headers=mh).json()["minio_key"] == f["minio_key"]


def test_file_rename_follows_upload_rule(client: TestClient) -> None:
    """진행 중 회차: 그 통제의 책임자 가능 · 외부감사인·무역할 403."""
    ctrl, cyc = _setup("F2")
    oh = _login(client, "eg-owner-F2@acme.example", PW)
    fid = _upload(client, oh, cyc, ctrl).json()["id"]
    r = client.patch(f"/api/evidence/files/{fid}", headers=oh, json={"filename": "새이름.pdf"})
    assert r.status_code == 200 and r.json()["filename"] == "새이름.pdf"
    for email in ("eg-ext@acme.example", "eg-plain@acme.example"):
        h = _login(client, email, PW)
        assert client.patch(f"/api/evidence/files/{fid}", headers=h,
                            json={"filename": "바꿈.pdf"}).status_code == 403


def test_file_rename_locked_in_closed_cycle(client: TestClient) -> None:
    """마감 회차: 통제책임자 403, `icfr_manager` 는 가능(업로드와 같다)."""
    ctrl, cyc = _setup("F3", status=CYCLE_CLOSED)
    mh = _login(client, "eg-mgr@acme.example", PW)
    fid = _upload(client, mh, cyc, ctrl).json()["id"]
    oh = _login(client, "eg-owner-F3@acme.example", PW)
    r = client.patch(f"/api/evidence/files/{fid}", headers=oh, json={"filename": "마감후.pdf"})
    assert r.status_code == 403 and "내부회계관리자만" in r.json()["detail"]
    assert client.patch(f"/api/evidence/files/{fid}", headers=mh,
                        json={"filename": "정정.pdf"}).status_code == 200


# ── 레거시 증빙(회차 없음): icfr_manager 만 ────────────────

def test_legacy_evidence_only_icfr_manager_can_delete_or_rename(client: TestClient) -> None:
    _setup("LG")
    db = TestingSessionLocal()
    try:
        mgr = db.query(User).filter(User.email == "eg-mgr@acme.example").one()
        legacy = EvidenceFile(filename="레거시.pdf", mime_type="application/pdf", size_bytes=1,
                              uploaded_by_id=mgr.id, tenant_id=DEFAULT_TENANT_ID)
        db.add(legacy)
        db.commit()
        fid = str(legacy.id)
    finally:
        db.close()
    oh = _login(client, "eg-owner-LG@acme.example", PW)   # 역할 없음 — require_write 는 통과한다
    r = client.delete(f"/api/evidence/files/{fid}", headers=oh)
    assert r.status_code == 403 and "내부회계관리자만" in r.json()["detail"]
    assert client.patch(f"/api/evidence/files/{fid}", headers=oh,
                        json={"filename": "x.pdf"}).status_code == 403
    mh = _login(client, "eg-mgr@acme.example", PW)
    assert client.delete(f"/api/evidence/files/{fid}", headers=mh).status_code == 204
