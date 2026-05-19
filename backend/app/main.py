import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import IntegrityError

from app.config import get_settings
from app.core.database import SessionLocal
from app.core.exceptions import (
    validation_exception_handler,
    integrity_exception_handler,
    unhandled_exception_handler,
)
from app.api import health, auth
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

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router)
    app.include_router(auth.router)

    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(IntegrityError, integrity_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)

    return app


app = create_app()
