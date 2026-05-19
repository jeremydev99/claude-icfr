"""
IUC (Information Used in Control) 모듈 API.

Phase 0: placeholder 엔드포인트만.
Phase 3: IUC 리포트 등록, 평가 자동 연결.

자세한 명세: ClaudeICFR.md 섹션 4.5 참조.
"""
from fastapi import APIRouter
from app.core.deps import CurrentUser

router = APIRouter(prefix="/api/iuc", tags=["iuc"])


@router.get("/info")
def get_module_info(user: CurrentUser) -> dict:
    """IUC 모듈 정보 — Phase 0 placeholder."""
    return {
        "module": "iuc",
        "name_kr": "IUC",
        "phase_0_status": "골조만",
        "phase_3_features": [
            "IUC 리포트 등록",
            "평가 자동 연결",
        ],
        "available_in_phase_1": False,
    }
