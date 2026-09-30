import { describe, expect, it } from 'vitest'
import {
  STANDARD_TEMPLATE,
  TOTAL_COLUMNS,
  buildColumns,
  calendarToOffset,
  currentFiscalYear,
  formatOffsetRange,
  offsetToCalendar,
  periodToSpan,
  phasesAt,
  startMonthFromPolicies,
  todayOffset,
} from './schedule.pure'

describe('schedule.pure', () => {
  it('템플릿 오프셋이 그리드 범위 안에 있다', () => {
    for (const p of STANDARD_TEMPLATE) {
      expect(p.start).toBeGreaterThanOrEqual(1)
      expect(p.end).toBeLessThanOrEqual(TOTAL_COLUMNS)
      expect(p.start).toBeLessThanOrEqual(p.end)
    }
  })

  it('시작월 정책 파싱 — 없거나 잘못되면 1', () => {
    expect(startMonthFromPolicies(undefined)).toBe(1)
    expect(startMonthFromPolicies([{ policy_key: 'fiscal_year_start_month', policy_value: '4' }])).toBe(4)
    expect(startMonthFromPolicies([{ policy_key: 'fiscal_year_start_month', policy_value: '13' }])).toBe(1)
  })

  it('회계연도 판정 — 시작월 이전이면 전년도', () => {
    expect(currentFiscalYear(new Date(2026, 2, 1), 4)).toBe(2025)
    expect(currentFiscalYear(new Date(2026, 3, 1), 4)).toBe(2026)
    expect(currentFiscalYear(new Date(2026, 0, 1), 1)).toBe(2026)
  })

  it('오프셋 ↔ 달력 변환', () => {
    expect(offsetToCalendar(2026, 1, 1)).toEqual({ year: 2026, month: 1 })
    expect(offsetToCalendar(2026, 1, 13)).toEqual({ year: 2027, month: 1 })
    expect(offsetToCalendar(2026, 4, 10)).toEqual({ year: 2027, month: 1 })
    expect(calendarToOffset(2026, 4, 2027, 1)).toBe(10)
    expect(calendarToOffset(2026, 1, 2025, 12)).toBe(0)
  })

  it('컬럼 15개, 13번째부터 익년', () => {
    const cols = buildColumns(2026, 1)
    expect(cols).toHaveLength(15)
    expect(cols[12]).toMatchObject({ year: 2027, month: 1, nextYear: true })
    expect(cols[11].nextYear).toBe(false)
  })

  it('기간 표시', () => {
    expect(formatOffsetRange(2026, 1, 10, 13)).toBe('2026.10 ~ 2027.01')
    expect(formatOffsetRange(2026, 1, 3, 3)).toBe('2026.03')
  })

  it('이번 달 할 일 — 9월(1월 시작)은 미비점 개선만', () => {
    const o = todayOffset(2026, 1, new Date(2026, 8, 30))
    expect(o).toBe(9)
    expect(phasesAt(o).map((p) => p.id)).toEqual(['remediation'])
    expect(todayOffset(2020, 1, new Date(2026, 8, 30))).toBeNull()
  })

  it('회차 기간 → 그리드 범위(잘라냄)', () => {
    expect(periodToSpan(2026, 1, '2026-03-01', '2026-05-31')).toEqual({ start: 3, end: 5 })
    expect(periodToSpan(2026, 1, '2025-11-01', '2026-02-28')).toEqual({ start: 1, end: 2 })
    expect(periodToSpan(2026, 1, '2024-01-01', '2024-12-31')).toBeNull()
  })
})
