"""
공통 미들웨어 — 요청 ID, 감사 로그.

ICFR 시스템은 외부감사 추적성이 필수 (ADR 다수).
Phase 0: 콘솔 감사 로그.
Phase 1+: audit_logs 테이블 저장 예정 (ClaudeICFR.md 섹션 5.2 그룹 I).
"""
import logging
import time
import uuid
from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("icfr.audit")


class RequestIDMiddleware(BaseHTTPMiddleware):
    """모든 요청에 X-Request-ID 헤더 부여 + 응답에도 포함.

    외부감사 시 특정 요청을 로그에서 추적할 수 있도록.
    """

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


class AuditLogMiddleware(BaseHTTPMiddleware):
    """모든 API 호출을 감사 로그로 기록."""

    EXCLUDED_PATHS = {"/docs", "/redoc", "/openapi.json", "/api/health"}

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        if any(request.url.path.startswith(p) for p in self.EXCLUDED_PATHS):
            return await call_next(request)

        start_time = time.time()
        response = await call_next(request)
        duration_ms = int((time.time() - start_time) * 1000)

        request_id = getattr(request.state, "request_id", "unknown")
        client_ip = request.client.host if request.client else "unknown"

        logger.info(
            "audit method=%s path=%s status=%d duration_ms=%d ip=%s request_id=%s",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
            client_ip,
            request_id,
        )
        return response
