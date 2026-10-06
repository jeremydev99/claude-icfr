"""재무제표 기간 → 회계연도 (2026-10-06). **회계연도 N = N년에 시작하는 회계연도**(평가 회차·일정과 같은 규칙,
services/assessment_period.py). 표제의 기간은 끝나는 날(재무상태표 "○년 ○월 ○일 현재", 손익 "~ ○년 ○월 ○일까지")로
적히므로, **마지막 날짜**를 회계연도로 바꾼다 — 12월 결산은 끝나는 해 그대로, 3월 결산은 2026년 3월 31일 → 2025 회계연도.

파서는 DB 를 모른다 — API 가 회계연도 시작월을 이 문맥에 넣고 파싱한다(`with fiscal_start(m):`). 넣지 않으면 1월(12월 결산).
"""
from __future__ import annotations

import re
from contextlib import contextmanager
from contextvars import ContextVar

_START: ContextVar[int] = ContextVar("fs_fiscal_start_month", default=1)
_DATE_RE = re.compile(r"(\d{4})\s*[년.\-/]\s*(\d{1,2})(?!\d)")
_YEAR_RE = re.compile(r"(\d{4})\s*년")


@contextmanager
def fiscal_start(month: int):
    tok = _START.set(month if 1 <= month <= 12 else 1)
    try:
        yield
    finally:
        _START.reset(tok)


def fiscal_year_of(year: int, month: int, start_month: int | None = None) -> int:
    """(연, 월)이 속한 회계연도. 시작월 이후면 그 해, 이전이면 전년도에 시작한 회계연도."""
    s = start_month or _START.get()
    return year if month >= s else year - 1


def fiscal_year_from_text(text: str) -> int | None:
    """기간 문구 → 회계연도. 날짜(연·월)가 있으면 **마지막 날짜** 기준, 연도만 있으면 그 연도(회계연도 표기로 본다)."""
    dates = _DATE_RE.findall(text or "")
    if dates:
        y, m = dates[-1]
        if 1 <= int(m) <= 12:
            return fiscal_year_of(int(y), int(m))
    ys = _YEAR_RE.findall(text or "")
    return int(ys[-1]) if ys else None
