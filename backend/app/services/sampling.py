"""필요 샘플 수 — 회차 종류 × 통제 (2026-10-15, 마스터 결정). 순수 함수.

| 경우 | 필요 수 |
|---|---|
| 설계평가 회차 | 1 (walkthrough) |
| 운영평가 + RCM 표본수 있음 | **RCM 표본수** — 감사인과 협의한 값이 우선 |
| 운영평가 + 표본수 없음 + 자동통제(auto_manual='A') | 1 — 시스템은 설정대로 매번 같게 동작한다 |
| 운영평가 + 표본수 없음 + 수동 | 통제 수행 주기 기준표(실무 관행의 하한) |

필요 수보다 적게는 제출할 수 없다(마스터 결정). 더 많이는 허용.
"""
from __future__ import annotations

from app.models.assessment import CYCLE_DESIGN

# 통제 수행 주기 → 권장 표본 수(실무 관행의 하한). RCM 표본수가 비었을 때만 쓴다
SAMPLE_BY_FREQUENCY = {"A": 1, "Q": 2, "M": 2, "W": 5, "D": 20, "O": 25}
AUTOMATED = "A"


def required_samples(cycle_kind: str, control: dict | None) -> int:
    if cycle_kind == CYCLE_DESIGN or control is None:
        return 1
    n = control.get("sample_size")
    if isinstance(n, int) and n > 0:
        return n
    if control.get("auto_manual") == AUTOMATED:
        return 1
    return SAMPLE_BY_FREQUENCY.get(control.get("frequency") or "", 1)


def basis(cycle_kind: str, control: dict | None) -> str:
    """필요 수의 근거 — 화면에 그대로 보인다."""
    if cycle_kind == CYCLE_DESIGN or control is None:
        return "설계평가 1건"
    n = control.get("sample_size")
    if isinstance(n, int) and n > 0:
        return "RCM 표본수"
    if control.get("auto_manual") == AUTOMATED:
        return "자동통제 1건"
    return "수행 주기 기준(RCM 표본수 없음)"
