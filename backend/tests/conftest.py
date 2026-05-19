import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import create_app
from app.models.base import Base
from app.core.database import get_db
from app.models.user import User
from app.core.security import hash_password

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
    """테스트 DB에 admin 계정을 생성 (없으면)."""
    existing = db.query(User).filter(User.email == "admin@acme.example").first()
    if not existing:
        admin = User(
            email="admin@acme.example",
            hashed_password=hash_password("admin123"),
            display_name="System Administrator",
            role="admin",
            is_active=True,
        )
        db.add(admin)
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
