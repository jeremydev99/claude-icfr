"""재무제표 결재 테스트 도우미 (ADR-0038 2-2) — 확정은 결재선으로만 된다.

`confirm` = 책임관리자 검토 요청 → 마스터 승인(경로 master). 책임관리자는 `h` 의 테넌트에 자동으로 만든다.
마스터 혼자 확정하던 `/finalize`·`/reopen` 은 없어졌다.
"""
from uuid import UUID

from fastapi.testclient import TestClient

from app.core.security import hash_password
from app.core.tenant_context import DEFAULT_TENANT_ID, reset_active_tenant, set_active_tenant
from app.models.tenant import UserTenantAccess
from app.models.user import User
from app.models.user_mgmt import UserRole
from tests.conftest import TestingSessionLocal

PW = "pw123456"


def lead_headers(client: TestClient, h: dict) -> dict:
    """`h` 와 같은 테넌트의 책임관리자(icfr_lead) 헤더."""
    tid = UUID(h["X-Tenant-Id"]) if "X-Tenant-Id" in h else DEFAULT_TENANT_ID
    email = f"fs-lead-{tid.hex[:8]}@acme.example"
    db = TestingSessionLocal()
    try:
        u = db.query(User).filter(User.email == email).first()
        if u is None:
            u = User(email=email, hashed_password=hash_password(PW), display_name="책임관리자", role="user",
                     is_active=True)
            db.add(u)
            db.commit()
        if db.query(UserTenantAccess).filter(UserTenantAccess.user_id == u.id,
                                             UserTenantAccess.tenant_id == tid).first() is None:
            db.add(UserTenantAccess(user_id=u.id, tenant_id=tid, role="user"))
            db.commit()
        tok = set_active_tenant(tid)
        try:
            if db.query(UserRole).filter(UserRole.user_id == u.id, UserRole.role_name == "icfr_lead",
                                         UserRole.is_deleted == False).first() is None:  # noqa: E712
                db.add(UserRole(user_id=u.id, role_name="icfr_lead"))
                db.commit()
        finally:
            reset_active_tenant(tok)
    finally:
        db.close()
    r = client.post("/api/auth/login", data={"username": email, "password": PW})
    assert r.status_code == 200, r.text
    out = {"Authorization": "Bearer " + r.json()["access_token"]}
    if "X-Tenant-Id" in h:
        out["X-Tenant-Id"] = h["X-Tenant-Id"]
    return out


def submit(client: TestClient, sid, h: dict, reason: str | None = None):
    return client.post(f"/api/fs/statements/{sid}/transition", headers=h,
                       json={"to_status": "review", "reason": reason})


def confirm(client: TestClient, sid, master: dict, reason: str = "결산 확정"):
    """책임관리자 검토 요청 → 마스터 승인. 검토 요청이 실패하면 그 응답을 돌려준다."""
    r = submit(client, sid, lead_headers(client, master))
    if r.status_code != 200:
        return r
    return client.post(f"/api/fs/statements/{sid}/transition", headers=master,
                       json={"to_status": "confirmed", "reason": reason})


def reopen(client: TestClient, sid, master: dict, reason: str):
    """책임관리자 재오픈 요청 → 마스터 승인."""
    r = client.post(f"/api/fs/statements/{sid}/reopen-requests", headers=lead_headers(client, master),
                    json={"reason": reason})
    if r.status_code != 201:
        return r
    rid = r.json()["governance"]["pending_reopen"]["id"]
    return client.post(f"/api/fs/statements/{sid}/reopen-requests/{rid}/decide", headers=master,
                       json={"approve": True})


def withdraw(client: TestClient, sid, h: dict):
    return client.post(f"/api/fs/statements/{sid}/transition", headers=h, json={"to_status": "draft"})
