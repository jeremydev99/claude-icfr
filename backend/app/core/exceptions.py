import logging
from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

logger = logging.getLogger(__name__)


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors()},
    )


async def integrity_exception_handler(request: Request, exc: IntegrityError) -> JSONResponse:
    logger.error(f"IntegrityError: {exc}")
    return JSONResponse(
        status_code=409,
        content={"detail": "데이터 무결성 제약 위반 (중복 또는 참조 오류)"},
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "서버 내부 오류가 발생했습니다"},
    )
