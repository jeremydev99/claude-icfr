"""스코핑 계산 — 양적 중요성·양적/질적 판정·결론 (ADR-0034 §2.3·§2.4, 6-1).

**원천 수식을 그대로 옮긴다.** 전부 순수 함수다(DB 를 모른다) — 테스트가 원천 캐시값과 바로 대조한다.

    벤치마크 산출액 = ROUND(기준값 × 비율, 0)
    전반중요성      = ROUND(벤치마크 산출액, -3)
    수행중요성      = ROUND(전반중요성 × 설정율, 0)

**반올림은 Excel `ROUND` 와 같아야 한다.** Excel 은 0.5 를 **0 에서 멀어지는 쪽**으로 올린다
(음수도 마찬가지 — ROUND(-2.5,0) = -3). Python `round()` 는 은행가 반올림(짝수 쪽)이라
`round(2.5) == 2` 가 되어 한 원이 달라진다. 그래서 `Decimal.quantize(ROUND_HALF_UP)` 를 쓴다
— decimal 의 HALF_UP 은 부호와 무관하게 "절댓값 기준으로 올림"이라 Excel 과 같다.

**float 를 쓰지 않는다.** 입력은 정수(원) 또는 Decimal 이다.
"""
from decimal import ROUND_HALF_UP, Decimal

from app.models.scoping import (
    QUAL_COMPARISON_GT,
    QUAL_FACTORS,
    QUANT_APPLICABLE_STATEMENTS,
    RATING_SCORES,
)

# 판정 결과 값
Y = "Y"
N = "N"
NA = "na"   # 해당 없음 — 주석·현금흐름의 양적 판정. **미평가(None)와 다르다**


def excel_round(value: Decimal | int, digits: int) -> Decimal:
    """Excel `ROUND(value, digits)`. digits 가 음수면 정수부 자리에서 반올림한다(-3 = 천 단위)."""
    exp = Decimal(1).scaleb(-digits)          # digits=0 → 1, digits=-3 → 1E+3, digits=2 → 0.01
    return Decimal(value).quantize(exp, rounding=ROUND_HALF_UP) if digits >= 0 else \
        (Decimal(value) / exp).quantize(Decimal(1), rounding=ROUND_HALF_UP) * exp


def benchmark_amount(base: int | None, rate: Decimal | None) -> int | None:
    """벤치마크 산출액 = ROUND(기준값 × 비율, 0). 재료가 하나라도 없으면 None."""
    if base is None or rate is None:
        return None
    return int(excel_round(Decimal(base) * Decimal(rate), 0))


def overall_materiality(bench: int | None) -> int | None:
    """전반중요성 = ROUND(벤치마크 산출액, -3) — 천원 단위 반올림."""
    return None if bench is None else int(excel_round(bench, -3))


def performance_materiality(overall: int | None, smt_rate: Decimal | None) -> int | None:
    """수행중요성(SMT) = ROUND(전반중요성 × 설정율, 0)."""
    if overall is None or smt_rate is None:
        return None
    return int(excel_round(Decimal(overall) * Decimal(smt_rate), 0))


def adjusted_base(pretax: int | None, adjustments: list[int]) -> int | None:
    """조정세전순이익 = 세전이익 + Σ조정. **조정은 부호가 붙은 금액을 더한다**(감소 조정은 음수)."""
    return None if pretax is None else pretax + sum(adjustments)


def out_of_range(value: Decimal | None, bounds: tuple[str | None, str | None] | None) -> bool:
    """가이드 범위 밖이면 True. 범위가 없으면(매출액 등) 판정하지 않는다 — False."""
    if value is None or bounds is None:
        return False
    lo, hi = bounds
    return (lo is not None and Decimal(value) < Decimal(lo)) or \
        (hi is not None and Decimal(value) > Decimal(hi))


# ── 계정 판정 ─────────────────────────────────────────────

def quantitative(statement_type: str, amount: int | None, smt: int | None) -> str | None:
    """양적 유의 = |당기 금액| ≥ 수행중요성.

    - 주석·현금흐름 → `NA`(해당 없음). 원천 각주가 그렇게 정했다
    - 금액 또는 수행중요성이 없으면 → None(미평가)
    """
    if statement_type not in QUANT_APPLICABLE_STATEMENTS:
        return NA
    if amount is None or smt is None:
        return None
    return Y if abs(amount) >= smt else N


def qualitative_average(ratings: dict | None) -> Decimal | None:
    """10요소 평균. **하나라도 미입력이면 None** — 원천은 빈칸을 0 으로 합산해 평균을 끌어내렸다.
    평가하지 않은 것이 "중요하지 않음"으로 나오는 과소평가다(ADR-0034 §2.4)."""
    ratings = ratings or {}
    scores = [RATING_SCORES.get(ratings.get(f)) for f in QUAL_FACTORS]
    if any(s is None for s in scores):
        return None
    return Decimal(sum(scores)) / Decimal(len(QUAL_FACTORS))


def qualitative(ratings: dict | None, threshold: Decimal, comparison: str) -> str | None:
    """질적 유의 — 평균이 기준값 이상(기본) 또는 초과. 미입력이 있으면 None(미평가)."""
    avg = qualitative_average(ratings)
    if avg is None:
        return None
    if comparison == QUAL_COMPARISON_GT:
        return Y if avg > threshold else N
    return Y if avg >= threshold else N   # 기본(QUAL_COMPARISON_GE) — 이상


def conclusion(quant: str | None, qual: str | None) -> str | None:
    """유의성 결론 = 양적 OR 질적.

    - 하나라도 Y → Y
    - 양적 해당 없음 → 질적 결과 그대로(미평가면 미평가)
    - 그 외 하나라도 미평가 → 미평가 (양적 N + 질적 미평가 = 미평가)
    - 둘 다 N → N
    """
    if quant == Y or qual == Y:
        return Y
    if quant == NA:
        return qual
    if quant is None or qual is None:
        return None
    return N


def final_conclusion(computed: str | None, manual: str | None) -> str | None:
    """수동 판정이 있으면 그것이 최종이다. **계산 결론은 따로 보존된다**(둘 다 응답에 나간다)."""
    return manual if manual is not None else computed

