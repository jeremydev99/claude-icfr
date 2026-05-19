import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import create_app
from app.models.base import Base
from app.core.database import get_db

SQLITE_URL = "sqlite:///./test.db"

engine = create_engine(SQLITE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="session")
def app():
    Base.metadata.create_all(bind=engine)
    application = create_app()
    application.dependency_overrides[get_db] = override_get_db
    yield application
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="session")
def client(app):
    with TestClient(app) as c:
        yield c
