"""회차 기간 제안 — ADR-0032 §2.2, 3-2.

**제안값일 뿐 강제하지 않는다.** 담당자가 조정할 수 있어야 하므로, 요청에
`period_start`/`period_end` 가 오면 그 값을 그대로 쓴다. 여기 계산은 미전송 시의
기본값이다.

`fiscal_year_start_month` 는 **회계연도가 시작하는 달**이다(결산월이 아니다).
12월 결산 회사는 1(1/1~12/31), 3월 결산 회사는 4(4/1~3/31 → 1분기 4/1~6/30).
이 값은 `tenant_policies` 에 있다(전용 컬럼을 만들면 3-3 에서 또 마이그레이션이 필요).

주(weekly)는 ISO 주 대신 **회계연도 시작일로부터 7일 단위**로 센다. ISO 주는 연도
경계가 회계연도와 어긋나 "1주차"가 전년도에 걸치는 일이 생긴다.
"""
from calendar import monthrange
from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.models.role_assignment import (
    DEFAULT_FISCAL_YEAR_START_MONTH,
    POLICY_FISCAL_YEAR_START_MONTH,
    TenantPolicy,
)

# 주기별 1회계연도 내 회차 수. weekly 는 가변이라 별도 처리.
_PERIODS_PER_YEAR = {
    "monthly": 12,
    "quarterly": 4,
    "semiannual": 2,
    "annual": 1,
}


def fiscal_year_start_month(db: Session) -> int:
    """테넌트 회계연도 시작월. 미설정·비정상 값이면 기본 1.

    정책은 문자열 저장이라 파싱한다. **잘못된 값에 예외를 던지지 않는다** — 설정 하나가
    깨졌다고 회차 생성 전체가 막히면 안 된다. 기본값으로 떨어뜨리고 진행한다.
    """
    row = db.query(TenantPolicy).filter(
        TenantPolicy.policy_key == POLICY_FISCAL_YEAR_START_MONTH,
        TenantPolicy.is_deleted == False,  # noqa: E712
    ).first()
    if row is None:
        return DEFAULT_FISCAL_YEAR_START_MONTH
    try:
        month = int(row.policy_value)
    except (TypeError, ValueError):
        return DEFAULT_FISCAL_YEAR_START_MONTH
    return month if 1 <= month <= 12 else DEFAULT_FISCAL_YEAR_START_MONTH


def _add_months(d: date, months: int) -> date:
    """월 단위 이동. 말일 보정 포함(1/31 + 1개월 = 2/28|29)."""
    total = d.month - 1 + months
    year = d.year + total // 12
    month = total % 12 + 1
    return date(year, month, min(d.day, monthrange(year, month)[1]))


def current_fiscal_year(today: date, start_month: int) -> int:
    """오늘이 속한 회계연도. 시작월 이전이면 전년도 회계연도다."""
    return today.year if today.month >= start_month else today.year - 1


def suggest_period(frequency: str, start_month: int, fiscal_year: int,
                   period_index: int) -> tuple[date, date]:
    """(period_start, period_end). end 는 다음 구간 시작 하루 전 — 경계가 겹치지 않는다."""
    fy_start = date(fiscal_year, start_month, 1)

    if frequency == "weekly":
        start = fy_start + timedelta(days=7 * (period_index - 1))
        return start, start + timedelta(days=6)

    per_year = _PERIODS_PER_YEAR.get(frequency, 1)
    months = 12 // per_year
    start = _add_months(fy_start, months * (period_index - 1))
    return start, _add_months(start, months) - timedelta(days=1)


def current_period_index(frequency: str, today: date, start_month: int,
                         fiscal_year: int) -> int:
    """오늘이 회계연도 내 몇 번째 구간인가. 회차 생성 시 기본 제안에 쓴다."""
    fy_start = date(fiscal_year, start_month, 1)
    if today < fy_start:
        return 1
    if frequency == "weekly":
        return (today - fy_start).days // 7 + 1
    per_year = _PERIODS_PER_YEAR.get(frequency, 1)
    months_elapsed = (today.year - fy_start.year) * 12 + (today.month - fy_start.month)
    return months_elapsed // (12 // per_year) + 1
