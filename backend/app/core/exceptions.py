import logging
from fastapi import Request


class ICFRException(Exception):
    """ICFR 도메인 예외 — status_code + detail 로 JSONResponse 변환."""

    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)
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
