"""
Scoping 모듈 API.

Phase 0: placeholder 엔드포인트만.
Phase 2: 정량·정성 평가, 유의계정 식별, 평가대상 통제 산출.

자세한 명세: ClaudeICFR.md 섹션 4.3 참조.
"""
from fastapi import APIRouter
from app.core.deps import CurrentUser

router = APIRouter(prefix="/api/scoping", tags=["scoping"])


@router.get("/info")
def get_module_info(user: CurrentUser) -> dict:
    """Scoping 모듈 정보 — Phase 0 placeholder."""
    return {
        "module": "scoping",
        "name_kr": "Scoping",
        "phase_0_status": "골조만",
        "phase_2_features": [
            "정량·정성 평가",
            "유의계정 식별",
            "평가대상 통제 산출",
        ],
        "available_in_phase_1": False,
    }
