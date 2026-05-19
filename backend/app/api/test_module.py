"""
Test (설계·운영평가) 모듈 API.

Phase 0: placeholder 엔드포인트만.
Phase 1: 평가 계획 수동 등록, 운영평가 결과 입력, Pass/Fail, 단순 검토 (A-1안).
Phase 1.5: 자동 샘플 추출, 자동 미비점 등록, 재테스트, 설계평가.

파일명이 test_module.py인 이유: Python 네이밍 충돌 방지 (test_*.py는 pytest가 수집).
자세한 명세: ClaudeICFR.md 섹션 4.11 참조.
"""
from fastapi import APIRouter
from app.core.deps import CurrentUser

router = APIRouter(prefix="/api/test", tags=["test_module"])


@router.get("/info")
def get_module_info(user: CurrentUser) -> dict:
    """Test 모듈 정보 — Phase 0 placeholder."""
    return {
        "module": "test_module",
        "name_kr": "Test (평가)",
        "phase_0_status": "골조만",
        "phase_1_features": [
            "평가 계획 수동 등록",
            "운영평가 결과 입력",
            "Pass/Fail 결론",
            "단순 검토 워크플로 (1단계)",
        ],
        "phase_1_excluded": [
            "자동 샘플 추출",
            "자동 미비점 등록 연동",
            "재테스트",
            "설계평가",
        ],
        "available_in_phase_1": True,
    }
