"""
Report 모듈 API.

Phase 0: placeholder 엔드포인트만.
Phase 3: 이사회 보고서 자동 초안, PBC 패키지, 결재, 잠금.

자세한 명세: ClaudeICFR.md 섹션 4.10 참조.
"""
from fastapi import APIRouter
from app.core.deps import CurrentUser

router = APIRouter(prefix="/api/report", tags=["report"])


@router.get("/info")
def get_module_info(user: CurrentUser) -> dict:
    """Report 모듈 정보 — Phase 0 placeholder."""
    return {
        "module": "report",
        "name_kr": "Report",
        "phase_0_status": "골조만",
        "phase_3_features": [
            "이사회 보고서 자동 초안",
            "PBC 패키지 생성",
            "결재 워크플로",
            "보고서 잠금 (Locked)",
        ],
        "available_in_phase_1": False,
    }
