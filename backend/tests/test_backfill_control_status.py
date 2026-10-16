"""통제현황 1회 보강 적재(13.9-134) — 안전장치 판정(순수 함수)."""
from scripts.backfill_control_status import plan


def _c(code, **kw):
    return {"code": code, "id": code, "description": "설명", "test_procedure": "절차", **kw}


def test_fills_only_empty_when_everything_else_matches() -> None:
    xl = [_c("A", control_status="현황A"), _c("B", control_status="현황B")]
    live = [_c("A"), _c("B", control_status="이미")]
    todo, problems = plan(xl, live)
    assert problems == [] and [(c["code"], v) for c, v in todo] == [("A", "현황A")]


def test_stops_when_other_fields_differ_or_codes_differ() -> None:
    _, problems = plan([_c("A", control_status="x", test_procedure="다른 절차")], [_c("A")])
    assert problems and "test_procedure" in problems[0]
    _, problems = plan([_c("A", control_status="x")], [_c("A"), _c("B")])
    assert problems and "코드 불일치" in problems[0]


def test_stops_when_column_missing() -> None:
    _, problems = plan([_c("A")], [_c("A")])
    assert any("통제현황 열" in p for p in problems)
