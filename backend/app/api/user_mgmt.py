"""
사용자/권한 관리 (User Management) 모듈 API.

Phase 0: placeholder 엔드포인트만.
Phase 1: 로그인 ID/PW, 사용자 CRUD, 단순 역할 (admin/user) (A-1안).
Phase 1.5: SoD, 위임, HR 연동.

자세한 명세: ClaudeICFR.md 섹션 4.8 참조.
ADR-0018: role 식별자는 소문자 (admin, user).
"""
from fastapi import APIRouter
from app.core.deps import CurrentUser

router = APIRouter(prefix="/api/users", tags=["user_mgmt"])


@router.get("/info")
def get_module_info(user: CurrentUser) -> dict:
    """사용자/권한 모듈 정보 — Phase 0 placeholder."""
    return {
        "module": "user_mgmt",
        "name_kr": "사용자/권한",
        "phase_0_status": "골조만",
        "phase_1_features": [
            "사용자 CRUD",
            "단순 역할 (admin/user)",
            "비밀번호 변경",
        ],
        "phase_1_excluded": [
            "SoD (직무 분리)",
            "위임",
            "HR 연동",
        ],
        "available_in_phase_1": True,
    }
