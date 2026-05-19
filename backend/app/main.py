import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

from app.config import get_settings
from app.core.database import SessionLocal
from app.core.exceptions import ICFRException
from app.core.middleware import AuditLogMiddleware, RequestIDMiddleware
from app.api import (
    health,
    auth,
    system,
    schedule,
    rcm,
    scoping,
    euc,
    iuc,
    remediation,
    evidence,
    user_mgmt,
    notification,
    report,
    test_module,
)
from app.seeds.bootstrap import bootstrap_admin

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    logger.info(f"Starting {settings.app_name} v{settings.app_version} ({settings.environment})")
    db = SessionLocal()
    try:
        bootstrap_admin(db)
        logger.info("Bootstrap admin completed")
    except Exception as e:
        logger.error(f"Bootstrap admin failed: {e}")
    finally:
        db.close()
    yield
    logger.info("Shutting down")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="ICFR (Internal Control over Financial Reporting) 통합 관리 시스템 API",
        lifespan=lifespan,
    )

    # Middlewares (등록 순서 중요 — 가장 나중에 add_middleware한 것이 가장 바깥쪽으로 실행)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RequestIDMiddleware)
    app.add_middleware(AuditLogMiddleware)

    # Exception Handlers
    @app.exception_handler(ICFRException)
    async def icfr_exception_handler(request: Request, exc: ICFRException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
            headers={"X-Request-ID": getattr(request.state, "request_id", "unknown")},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={"detail": exc.errors()},
            headers={"X-Request-ID": getattr(request.state, "request_id", "unknown")},
        )

    @app.exception_handler(IntegrityError)
    async def integrity_exception_handler(request: Request, exc: IntegrityError) -> JSONResponse:
        logger.error(f"IntegrityError: {exc}")
        return JSONResponse(
            status_code=409,
            content={"detail": "데이터 무결성 제약 위반 (중복 또는 참조 오류)"},
        )

    # Routers — 인증·헬스
    app.include_router(health.router)
    app.include_router(auth.router)

    # Routers — 시스템 메타
    app.include_router(system.router)

    # Routers — 11개 모듈
    app.include_router(schedule.router)
    app.include_router(rcm.router)
    app.include_router(scoping.router)
    app.include_router(euc.router)
    app.include_router(iuc.router)
    app.include_router(remediation.router)
    app.include_router(evidence.router)
    app.include_router(user_mgmt.router)
    app.include_router(notification.router)
    app.include_router(report.router)
    app.include_router(test_module.router)

    @app.get("/")
    def root() -> dict[str, str]:
        return {
            "name": settings.app_name,
            "version": settings.app_version,
            "docs": "/docs",
        }

    return app


app = create_app()
