"""
RCM 관리 모듈 API.

Phase 0: placeholder 엔드포인트만 (인증 검증용).
Phase 1: 통제 CRUD, 검색·필터, Excel 일괄, 단순 이력 (ADR-0007 A-1안).
Phase 1.5: 버전 관리, 변경 승인 워크플로.

자세한 명세: ClaudeICFR.md 섹션 4.2 참조.
"""
from fastapi import APIRouter
from app.core.deps import CurrentUser

router = APIRouter(prefix="/api/rcm", tags=["rcm"])


@router.get("/info")
def get_module_info(user: CurrentUser) -> dict:
    """RCM 모듈 정보 — Phase 0 placeholder."""
    return {
        "module": "rcm",
        "name_kr": "RCM 관리",
        "phase_0_status": "골조만",
        "phase_1_features": [
            "통제 CRUD",
            "검색·필터 (프로세스/어써션)",
            "Excel 일괄 업로드",
            "단순 이력",
        ],
        "phase_1_excluded": [
            "버전 관리 (스냅샷·Diff)",
            "변경 승인 워크플로",
        ],
        "available_in_phase_1": True,
    }
