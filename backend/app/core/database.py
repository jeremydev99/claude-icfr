from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings

settings = get_settings()

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 이벤트 리스너 등록 (import 부수효과). 모든 Session 에 부착된다.
# - audit_context: 감사 컬럼 자동 기록·행위자 fail-closed·bulk DML 차단 (ADR-0036)
# - tenant_context: 멀티테넌시 자동 격리 — before_flush(주입)·do_orm_execute(필터) (ADR-0025)
# 두 리스너는 서로 다른 컬럼만 건드려 실행 순서가 결과에 영향을 주지 않는다
# (tenant_context 는 다른 모듈이 먼저 import 할 수 있어 순서를 여기서 보장하지 않는다).
import app.core.audit_context  # noqa: E402,F401
import app.core.tenant_context  # noqa: E402,F401


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
