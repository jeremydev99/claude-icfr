from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator

from app.config import get_settings

settings = get_settings()

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 멀티테넌시 자동 격리 이벤트 리스너 등록 (import 부수효과 — ADR-0025).
# 모든 Session 에 before_flush(주입)·do_orm_execute(필터)가 부착된다.
import app.core.tenant_context  # noqa: E402,F401


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
