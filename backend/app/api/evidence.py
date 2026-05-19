"""
증빙 관리 (Evidence) 모듈 API.

Phase 0: placeholder 엔드포인트만.
Phase 1: 업로드/다운로드, 모듈 연결, 단순 검색 (파일명·태그) (A-1안).
Phase 3: PBC 빌더, 보존기간 알림.

자세한 명세: ClaudeICFR.md 섹션 4.7 참조.
"""
from fastapi import APIRouter
from app.core.deps import CurrentUser

router = APIRouter(prefix="/api/evidence", tags=["evidence"])


@router.get("/info")
def get_module_info(user: CurrentUser) -> dict:
    """증빙 관리 모듈 정보 — Phase 0 placeholder."""
    return {
        "module": "evidence",
        "name_kr": "증빙 관리",
        "phase_0_status": "골조만",
        "phase_1_features": [
            "파일 업로드/다운로드 (MinIO)",
            "모듈 연결 (RCM·Test·개선계획)",
            "단순 검색 (파일명·태그)",
        ],
        "phase_1_excluded": [
            "PBC 빌더",
            "보존기간 알림",
        ],
        "available_in_phase_1": True,
    }
