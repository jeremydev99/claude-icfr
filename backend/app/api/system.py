"""
시스템 전체 메타 정보 API.

Frontend(Regina)가 사이드바 메뉴·라우트를 동적으로 생성할 때 참조.
icon 필드: lucide-react 아이콘 이름 (shadcn/ui 호환).
"""
from fastapi import APIRouter
from app.core.deps import CurrentUser

router = APIRouter(prefix="/api/system", tags=["system"])

MODULES = [
    {
        "id": "schedule",
        "name_kr": "일정관리",
        "icon": "calendar",
        "phase_target": "Phase 2",
        "available_in_phase_1": False,
        "order": 1,
    },
    {
        "id": "rcm",
        "name_kr": "RCM 관리",
        "icon": "shield-check",
        "phase_target": "Phase 1",
        "available_in_phase_1": True,
        "order": 2,
    },
    {
        "id": "scoping",
        "name_kr": "Scoping",
        "icon": "target",
        "phase_target": "Phase 2",
        "available_in_phase_1": False,
        "order": 3,
    },
    {
        "id": "euc",
        "name_kr": "EUC",
        "icon": "file-spreadsheet",
        "phase_target": "Phase 3",
        "available_in_phase_1": False,
        "order": 4,
    },
    {
        "id": "iuc",
        "name_kr": "IUC",
        "icon": "file-text",
        "phase_target": "Phase 3",
        "available_in_phase_1": False,
        "order": 5,
    },
    {
        "id": "remediation",
        "name_kr": "개선계획",
        "icon": "wrench",
        "phase_target": "Phase 1",
        "available_in_phase_1": True,
        "order": 6,
    },
    {
        "id": "evidence",
        "name_kr": "증빙 관리",
        "icon": "paperclip",
        "phase_target": "Phase 1",
        "available_in_phase_1": True,
        "order": 7,
    },
    {
        "id": "user_mgmt",
        "name_kr": "사용자/권한",
        "icon": "users",
        "phase_target": "Phase 1",
        "available_in_phase_1": True,
        "order": 8,
    },
    {
        "id": "notification",
        "name_kr": "알림",
        "icon": "bell",
        "phase_target": "Phase 2",
        "available_in_phase_1": False,
        "order": 9,
    },
    {
        "id": "report",
        "name_kr": "Report",
        "icon": "file-bar-chart",
        "phase_target": "Phase 3",
        "available_in_phase_1": False,
        "order": 10,
    },
    {
        "id": "test_module",
        "name_kr": "Test (평가)",
        "icon": "clipboard-check",
        "phase_target": "Phase 1",
        "available_in_phase_1": True,
        "order": 11,
    },
]


@router.get("/modules")
def list_modules(user: CurrentUser) -> list[dict]:
    """ICFR 11개 모듈 목록. Frontend 사이드바 메뉴 생성용."""
    return MODULES


@router.get("/info")
def system_info(user: CurrentUser) -> dict:
    """시스템 전체 정보."""
    return {
        "name": "ICFR System",
        "version": "0.1.0",
        "current_phase": "Phase 0",
        "module_count": len(MODULES),
        "active_in_phase_1": sum(1 for m in MODULES if m["available_in_phase_1"]),
    }
