import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import create_app
import app.models  # noqa: F401 — 모든 모델을 Base.metadata에 등록
from app.models.base import Base
from app.core.database import get_db
from app.models.user import User
from app.models.tenant import Tenant, UserTenantAccess
from app.core.security import hash_password
from app.core.tenant_context import (
    DEFAULT_TENANT_ID, DEFAULT_TENANT_CODE, DEFAULT_TENANT_NAME,
)

SQLITE_URL = "sqlite:///./test.db"

engine = create_engine(SQLITE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


def _seed_admin(db):
    """테스트 DB에 기본 tenant + admin 계정 + 접근 권한을 생성 (없으면)."""
    tenant = db.query(Tenant).filter(Tenant.id == DEFAULT_TENANT_ID).first()
    if not tenant:
        db.add(Tenant(
            id=DEFAULT_TENANT_ID, name=DEFAULT_TENANT_NAME,
            code=DEFAULT_TENANT_CODE, is_active=True,
        ))
        db.commit()

    admin = db.query(User).filter(User.email == "admin@acme.example").first()
    if not admin:
        admin = User(
            email="admin@acme.example",
            hashed_password=hash_password("admin123"),
            display_name="System Administrator",
            role="admin",
            is_active=True,
        )
        db.add(admin)
        db.commit()

    access = db.query(UserTenantAccess).filter(
        UserTenantAccess.user_id == admin.id,
        UserTenantAccess.tenant_id == DEFAULT_TENANT_ID,
    ).first()
    if not access:
        db.add(UserTenantAccess(user_id=admin.id, tenant_id=DEFAULT_TENANT_ID, role="admin"))
        db.commit()


@pytest.fixture(scope="session")
def app():
    Base.metadata.create_all(bind=engine)
    # 테스트 DB에 admin 시드
    db = TestingSessionLocal()
    try:
        _seed_admin(db)
    finally:
        db.close()

    application = create_app()
    application.dependency_overrides[get_db] = override_get_db
    yield application
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="session")
def client(app):
    with TestClient(app) as c:
        yield c
