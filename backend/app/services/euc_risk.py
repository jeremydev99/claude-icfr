"""EUC 위험 산출 — ADR-0033 §2.2(정정)·§2.3·§2.4, 5-1.

**사람은 재료 두 가지만 넣는다** — 파일 복잡도, 정보 항목별 중요성. 나머지는 여기서 산출한다:

    파일 중요성    = 연결된 **살아 있는** 정보 항목 중요성의 최고값
    위험 등급      = RISK_MATRIX[복잡도][파일 중요성]
    통제 식별 여부 = 위험 등급 ≥ 임계값(tenant_policies)

**저장하지 않고 조회할 때마다 계산한다**(ADR-0029 §2.2). 규모가 파일 수십 건이라 성능 문제가
없고, 저장하면 정보 항목 중요성이 바뀔 때마다 파일 값을 다시 맞춰야 한다. 임계값을 바꾸면
결과가 즉시 바뀌는 것도 이 방식이라야 된다.

재료가 하나라도 없으면 결과는 None(미평가)이다. **추정해서 채우지 않는다** — 원천 양식이
위험평가를 "Low" 로 적어 둔 것과 우리가 평가하지 않은 것은 다른 상태다(5-1 §2.3).
"""
from sqlalchemy.orm import Session

from app.models.euc import (
    COMPLEXITY_FORMULA,
    COMPLEXITY_MACRO_MODEL,
    COMPLEXITY_SIMPLE,
    DEFAULT_EUC_IDENTIFICATION_THRESHOLD,
    POLICY_EUC_IDENTIFICATION_THRESHOLD,
    RISK_GRADES,
    RISK_HIGH,
    RISK_LOW,
    RISK_MODERATE,
)
from app.models.iuc import IMPORTANCE_VALUES
from app.models.role_assignment import TenantPolicy

# **초기값이다. 근거가 있는 표준값이 아니다.** 출처는 ADR-0033 §2.3 의 2축 모델(복잡도 ×
# 중요성 — 국내외 EUC 위험평가 표준이 공통으로 쓰는 두 요인)이고, 각 칸의 등급은 5-1 에서
# 정한 출발점이다. 실무·감사인 협의로 조정될 수 있으며 **이 표 한 곳만 고치면 된다.**
#
#                    L          M          H
RISK_MATRIX: dict[str, dict[str, str]] = {
    COMPLEXITY_SIMPLE:      {"L": RISK_LOW,      "M": RISK_LOW,      "H": RISK_MODERATE},
    COMPLEXITY_FORMULA:     {"L": RISK_LOW,      "M": RISK_MODERATE, "H": RISK_HIGH},
    COMPLEXITY_MACRO_MODEL: {"L": RISK_MODERATE, "M": RISK_HIGH,     "H": RISK_HIGH},
}

# 중요성 서열 — H 가 가장 높다. `IMPORTANCE_VALUES` 의 순서(H, M, L)에서 만든다.
_IMPORTANCE_RANK = {v: len(IMPORTANCE_VALUES) - i for i, v in enumerate(IMPORTANCE_VALUES)}
_RISK_RANK = {v: i for i, v in enumerate(RISK_GRADES)}


def file_importance(importances: list[str | None]) -> str | None:
    """연결된 정보 항목 중요성의 최고값. **한 곳이라도 중요하게 쓰이면 그 파일은 중요하다.**

    미평가(None) 항목은 건너뛴다. 평가된 항목이 하나도 없으면 None.
    """
    rated = [i for i in importances if i in _IMPORTANCE_RANK]
    return max(rated, key=_IMPORTANCE_RANK.__getitem__) if rated else None


def risk_grade(complexity: str | None, importance: str | None) -> str | None:
    """복잡도 × 파일 중요성 → 위험 등급. 재료가 하나라도 없으면 None(미평가)."""
    if complexity is None or importance is None:
        return None
    return RISK_MATRIX.get(complexity, {}).get(importance)


def is_identified(grade: str | None, threshold: str) -> bool | None:
    """위험 등급이 임계값 이상이면 EUC 통제 식별 대상. 등급이 없으면 None(판정 불가)."""
    if grade is None:
        return None
    return _RISK_RANK[grade] >= _RISK_RANK[threshold]


def identification_threshold(db: Session) -> str:
    """테넌트 정책의 임계값. 없거나 목록 밖 값이면 기본값(moderate).

    값 검증은 정책 저장 시 한다(`api/role_assignment._assert_policy_value_valid`). 여기서
    다시 거르는 것은 저장 검증이 생기기 전의 값이 남아 있을 때 판정이 터지지 않게 하려는 것이다.
    """
    row = db.query(TenantPolicy).filter(
        TenantPolicy.policy_key == POLICY_EUC_IDENTIFICATION_THRESHOLD,
        TenantPolicy.is_deleted == False,  # noqa: E712
    ).first()
    value = row.policy_value if row else None
    return value if value in _RISK_RANK else DEFAULT_EUC_IDENTIFICATION_THRESHOLD
