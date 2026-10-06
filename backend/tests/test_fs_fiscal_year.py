"""재무제표 기간 → 회계연도 (2026-10-06) — 회계연도 N = N년에 시작하는 회계연도. 마지막 날짜·결산월 기준."""
from app.services.fs_upload.fiscal import fiscal_start, fiscal_year_from_text, fiscal_year_of


def test_december_close_unchanged() -> None:
    # 12월 결산(시작월 1) — 종전과 같다: 끝나는 해 = 회계연도
    assert fiscal_year_from_text("제26기 2025년 12월 31일 현재") == 2025
    assert fiscal_year_from_text("제26기 2025.01.01 ~ 2025.12.31") == 2025
    assert fiscal_year_from_text("제25기") is None
    assert fiscal_year_from_text("2024년") == 2024


def test_march_close_uses_start_year() -> None:
    with fiscal_start(4):   # 3월 결산 — 회계연도 2025 = 2025.04.01 ~ 2026.03.31
        assert fiscal_year_from_text("제26기 2026년 3월 31일 현재") == 2025
        # 손익은 시작일·종료일이 다 적혀도 마지막 날짜(종료일) 기준 → 재무상태표와 같은 연도
        assert fiscal_year_from_text("제26기 2025년 4월 1일부터 2026년 3월 31일까지") == 2025
        assert fiscal_year_from_text("제25기 2025.03.31 현재") == 2024
    assert fiscal_year_of(2026, 3, 4) == 2025 and fiscal_year_of(2026, 4, 4) == 2026
    # 문맥을 벗어나면 기본(1월)으로 돌아온다
    assert fiscal_year_from_text("2026년 3월 31일 현재") == 2026
