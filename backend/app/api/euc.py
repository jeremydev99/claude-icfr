"""
EUC (End User Computing) 모듈 API.

Phase 0: placeholder 엔드포인트만.
Phase 3: EUC 파일 등록, SHA-256 해시 점검, 변경 감지.

자세한 명세: ClaudeICFR.md 섹션 4.4 참조.
"""
from fastapi import APIRouter
from app.core.deps import CurrentUser

router = APIRouter(prefix="/api/euc", tags=["euc"])


@router.get("/info")
def get_module_info(user: CurrentUser) -> dict:
    """EUC 모듈 정보 — Phase 0 placeholder."""
    return {
        "module": "euc",
        "name_kr": "EUC",
        "phase_0_status": "골조만",
        "phase_3_features": [
            "EUC 파일 등록",
            "SHA-256 해시 점검",
            "변경 감지",
        ],
        "available_in_phase_1": False,
    }
