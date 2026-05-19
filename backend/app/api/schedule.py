"""
일정관리 모듈 API.

Phase 0: placeholder 엔드포인트만.
Phase 2: 연간 평가 일정 수립 (WBS), 마일스톤 추적, 담당자 배정.

자세한 명세: ClaudeICFR.md 섹션 4.1 참조.
"""
from fastapi import APIRouter
from app.core.deps import CurrentUser

router = APIRouter(prefix="/api/schedule", tags=["schedule"])


@router.get("/info")
def get_module_info(user: CurrentUser) -> dict:
    """일정관리 모듈 정보 — Phase 0 placeholder."""
    return {
        "module": "schedule",
        "name_kr": "일정관리",
        "phase_0_status": "골조만",
        "phase_2_features": [
            "연간 평가 일정 수립 (WBS)",
            "마일스톤 추적",
            "담당자 배정",
        ],
        "available_in_phase_1": False,
    }
