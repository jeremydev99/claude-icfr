"""
개선계획 (Remediation) 모듈 API.

Phase 0: placeholder 엔드포인트만.
Phase 1: 미비점 CRUD, 단순 심각도 3단계, 개선계획 서술형, 종결 처리 (A-1안).
Phase 1.5: 심각도 매트릭스, 마일스톤 추적, 이월 트래킹.

자세한 명세: ClaudeICFR.md 섹션 4.6 참조.
"""
from fastapi import APIRouter
from app.core.deps import CurrentUser

router = APIRouter(prefix="/api/remediation", tags=["remediation"])


@router.get("/info")
def get_module_info(user: CurrentUser) -> dict:
    """개선계획 모듈 정보 — Phase 0 placeholder."""
    return {
        "module": "remediation",
        "name_kr": "개선계획",
        "phase_0_status": "골조만",
        "phase_1_features": [
            "미비점 CRUD",
            "단순 심각도 3단계",
            "개선계획 서술형",
            "종결 처리",
        ],
        "phase_1_excluded": [
            "심각도 매트릭스",
            "마일스톤 추적",
            "이월 트래킹",
        ],
        "available_in_phase_1": True,
    }
