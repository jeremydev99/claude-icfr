"""
알림 (Notification) 모듈 API.

Phase 0: placeholder 엔드포인트만.
Phase 2: 이메일 (SMTP), 잔디 Webhook, 이벤트 기반 알림.

자세한 명세: ClaudeICFR.md 섹션 4.9 참조.
"""
from fastapi import APIRouter
from app.core.deps import CurrentUser

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
