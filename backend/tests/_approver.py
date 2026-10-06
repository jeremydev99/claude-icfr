"""두 번째 사용자(승인자) — 자기 승인 금지(13.9-94) 이후 승인 전이는 수행자와 다른 사람이 해야 한다."""
from fastapi.testclient import TestClient

from app.core.security import hash_password
from app.core.tenant_context import DEFAULT_TENANT_ID
from app.models.tenant import UserTenantAccess
from app.models.user import User
from tests.conftest import TestingSessionLocal

APPROVER_EMAIL = "approver@acme.example"
APPROVER_PW = "pw123456"


def approver_headers(client: TestClient) -> dict:
    db = TestingSessionLocal()
    try:
        u = db.query(User).filter(User.email == APPROVER_EMAIL).first()
        if u is None:
            u = User(email=APPROVER_EMAIL, hashed_password=hash_password(APPROVER_PW),
                     display_name="승인자", role="user", is_active=True)
            db.add(u)
            db.commit()
        if db.query(UserTenantAccess).filter(UserTenantAccess.user_id == u.id,
                                             UserTenantAccess.tenant_id == DEFAULT_TENANT_ID).first() is None:
            db.add(UserTenantAccess(user_id=u.id, tenant_id=DEFAULT_TENANT_ID, role="user"))
            db.commit()
    finally:
        db.close()
    resp = client.post("/api/auth/login", data={"username": APPROVER_EMAIL, "password": APPROVER_PW})
    assert resp.status_code == 200, resp.text
    return {"Authorization": "Bearer " + resp.json()["access_token"]}


def user_id_of(client: TestClient, headers: dict) -> str:
    return client.get("/api/auth/me", headers=headers).json()["id"]
