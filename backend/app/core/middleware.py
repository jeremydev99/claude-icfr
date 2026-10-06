"""
공통 미들웨어 — 요청 ID, 감사 로그.

ICFR 시스템은 외부감사 추적성이 필수 (ADR 다수).
콘솔 감사 로그 + DB `audit_logs`(상태 변경 요청·다운로드, 2026-10-06 — services/audit_log.py).
"""
import logging
import time
import uuid
from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from starlette.concurrency import run_in_threadpool
from starlette.middleware.base import BaseHTTPMiddleware

from app.services import audit_log as audit_svc

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
        # DB 감사 로그(2026-10-06) — 상태를 바꾸는 요청·다운로드. 실패해도 요청 결과는 그대로 돌려준다
        if audit_svc.should_log(request.method, request.url.path):
            try:
                await run_in_threadpool(self._persist, request, response.status_code, duration_ms, request_id)
            except Exception:  # noqa: BLE001 — 감사 로그 저장 실패가 업무 요청을 깨면 안 된다
                logger.exception("audit log persist failed path=%s", request.url.path)
        return response

    @staticmethod
    def _client_ip(request: Request) -> str | None:
        fwd = request.headers.get("x-forwarded-for")
        if fwd:
            return fwd.split(",")[0].strip()
        return request.headers.get("x-real-ip") or (request.client.host if request.client else None)

    def _persist(self, request: Request, status_code: int, duration_ms: int, request_id: str) -> None:
        """`get_db` 와 같은 경로로 세션을 얻는다 — 테스트의 의존성 교체(테스트 DB)도 그대로 따른다."""
        from app.core.database import get_db
        route = request.scope.get("route")
        route_path = getattr(route, "path", None) or request.url.path
        user_id = getattr(request.state, "audit_user_id", None) or audit_svc.user_from_auth(
            request.headers.get("authorization"))
        factory = request.app.dependency_overrides.get(get_db, get_db)
        gen = factory()
        db = next(gen)
        try:
            audit_svc.write(db, user_id=user_id, tenant_header=request.headers.get("x-tenant-id"),
                            method=request.method, route=route_path, path=request.url.path,
                            status_code=status_code, ip=self._client_ip(request),
                            user_agent=request.headers.get("user-agent"), duration_ms=duration_ms,
                            request_id=request_id)
        finally:
            gen.close()
