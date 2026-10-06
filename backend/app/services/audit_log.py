"""감사 로그 기록 규칙 — 무엇을 남기고 어떻게 부르는지(순수 함수) + 저장. 미들웨어와 테스트가 같은 규칙을 본다."""
from __future__ import annotations

import re
from uuid import UUID

# 경로 접두 → 모듈 이름(화면 표시). 긴 접두부터 본다
MODULES: list[tuple[str, str]] = [
    ("/api/control-links", "통제↔계정 연결"),
    ("/api/auth", "인증"),
    ("/api/users", "사용자·권한"),
    ("/api/external", "외부 사용자"),
    ("/api/invite", "외부 사용자"),
    ("/api/org", "조직·역할·정책"),
    ("/api/scoping", "스코핑"),
    ("/api/fs", "재무제표"),
    ("/api/rcm", "RCM"),
    ("/api/euc", "EUC"),
    ("/api/iuc", "IUC"),
    ("/api/assessment", "평가 회차"),
    ("/api/test", "테스트"),
    ("/api/remediation", "미비점·개선계획"),
    ("/api/evidence", "증빙"),
    ("/api/report", "보고서"),
    ("/api/proposals", "제안 결재"),
    ("/api/governance", "검토·승인"),
    ("/api/schedule", "일정"),
    ("/api/notification", "알림"),
    ("/api/help", "도움말"),
    ("/api/admin", "관리자"),
]

# 마지막 경로 조각(동사) → 동작 이름. 없으면 HTTP 메서드로 정한다
VERBS = {
    "login": "로그인", "logout": "로그아웃", "refresh": "토큰 갱신", "change-password": "비밀번호 변경",
    "approve": "승인", "finalize": "확정", "reopen": "재오픈", "review": "검토", "review-done": "검토 완료",
    "submit": "검토 요청", "return": "반려", "decide": "결정", "decide-pending": "일괄 결정", "transition": "상태 변경",
    "upload": "업로드", "attach": "결합", "revoke": "해지", "unlock": "잠금 해제", "reset-password": "비밀번호 초기화",
    "mfa-reset": "2단계 인증 초기화", "verify": "2단계 인증", "setup": "2단계 인증 등록", "enable": "2단계 인증 등록",
    "bulk": "일괄 처리", "auto": "자동 매칭", "accept": "초대 수락", "reload-from-fs": "재무제표에서 다시 불러오기",
    "not-applicable": "해당 없음 지정", "confirm": "확정", "download": "다운로드", "export": "내보내기",
}
METHOD_ACTION = {"POST": "등록", "PUT": "수정", "PATCH": "수정", "DELETE": "삭제", "GET": "조회"}
_UUID = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")
_SKIP = ("/api/health", "/docs", "/redoc", "/openapi.json")


def should_log(method: str, path: str) -> bool:
    """상태를 바꾸는 요청 전부 + 다운로드·내보내기 조회. 감사 로그 조회 자체는 남기지 않는다(조회가 로그를 불린다)."""
    if not path.startswith("/api/") or path.startswith(_SKIP):
        return False
    if method in ("POST", "PUT", "PATCH", "DELETE"):
        return True
    return method == "GET" and bool(re.search(r"/(download|export)(/|$)", path)) and "/audit-logs" not in path


def module_of(path: str) -> str:
    return next((name for prefix, name in MODULES if path.startswith(prefix)), "기타")


def action_of(method: str, route: str) -> str:
    segs = [s for s in route.split("/") if s and not s.startswith("{")]
    for s in reversed(segs[-2:]):
        if s in VERBS:
            return VERBS[s]
    return METHOD_ACTION.get(method, method)


def target_of(path: str) -> str | None:
    m = _UUID.findall(path)
    return m[-1] if m else None


def user_from_auth(header: str | None) -> UUID | None:
    if not header or not header.startswith("Bearer "):
        return None
    from app.core.security import decode_token
    p = decode_token(header[7:].strip())
    if not p or p.get("type") != "access":
        return None
    try:
        return UUID(p["sub"])
    except (KeyError, ValueError):
        return None


def write(db, *, user_id: UUID | None, tenant_header: str | None, method: str, route: str, path: str,
          status_code: int, ip: str | None, user_agent: str | None, duration_ms: int, request_id: str | None) -> None:
    """한 줄 저장. 실패해도 요청에는 영향을 주지 않는다(호출부가 예외를 삼킨다)."""
    from app.models.audit_log import AuditLog
    from app.models.tenant import UserTenantAccess
    from app.models.user import User
    email = name = None
    tenant: UUID | None = None
    if tenant_header:
        try:
            tenant = UUID(tenant_header)
        except ValueError:
            tenant = None
    if user_id is not None:
        u = db.get(User, user_id)
        if u is not None:
            email, name = u.email, u.display_name
        if tenant is None:
            acc = db.query(UserTenantAccess).filter(UserTenantAccess.user_id == user_id,
                                                    UserTenantAccess.is_deleted == False).first()  # noqa: E712
            tenant = acc.tenant_id if acc else None
    db.add(AuditLog(tenant_id=tenant, user_id=user_id, user_email=email, user_name=name, method=method,
                    route=route[:300], path=path[:500], module=module_of(path), action=action_of(method, route),
                    target_id=target_of(path), status_code=status_code, success=status_code < 400,
                    ip=(ip or "")[:64] or None, user_agent=(user_agent or "")[:300] or None,
                    duration_ms=duration_ms, request_id=(request_id or "")[:64] or None))
    db.commit()
