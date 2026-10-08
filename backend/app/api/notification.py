"""
알림 (Notification) 모듈 API.

Phase 0: placeholder 엔드포인트만.
Phase 2: 이메일 (SMTP), 잔디 Webhook, 이벤트 기반 알림.

자세한 명세: ClaudeICFR.md 섹션 4.9 참조.
"""
from fastapi import APIRouter, Depends

from app.core.deps import CurrentUser, require_admin
from app.models.user import User
from app.services import mailer

router = APIRouter(prefix="/api/notification", tags=["notification"])


@router.get("/info")
def get_module_info(user: CurrentUser) -> dict:
    """알림 모듈 정보 — Phase 0 placeholder."""
    return {
        "module": "notification",
        "name_kr": "알림",
        "phase_0_status": "골조만",
        "phase_2_features": [
            "이메일 발송 (SMTP)",
            "잔디 Webhook",
            "이벤트 기반 알림 (도메인 이벤트 구독)",
        ],
        "available_in_phase_1": False,
    }


@router.get("/mail/status")
def mail_status(user: CurrentUser) -> dict:
    """메일 발송 설정 여부 — 화면이 '메일로 보냄 / 링크를 직접 전달' 안내를 고르는 데 쓴다."""
    return {"configured": mailer.is_configured()}


@router.post("/mail/test")
def mail_test(admin: User = Depends(require_admin)) -> dict:
    """시험 메일을 요청한 시스템관리자 본인 주소로 보낸다."""
    m = mailer.test_mail(admin.email)
    return {"to": admin.email, "sent": m.sent, "error": m.error}
