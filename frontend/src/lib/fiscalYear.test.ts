import { describe, expect, it } from 'vitest'
import {
  describeClose, endMonthOf, fiscalEndKo, fiscalRange, fiscalYearOfDate, fyLabel, fyShort, startMonthOf,
} from './fiscalYear'

describe('회계연도 규칙', () => {
  it('결산월 ↔ 시작월', () => {
    expect(startMonthOf(12)).toBe(1)
    expect(startMonthOf(3)).toBe(4)
    expect(endMonthOf(1)).toBe(12)
    expect(endMonthOf(4)).toBe(3)
  })
  it('12월 결산 — 회계연도 = 그 해', () => {
    expect(fiscalRange(2026, 1)).toEqual({ start: '2026-01-01', end: '2026-12-31' })
    expect(fyLabel(2026, 1)).toBe('2026 회계연도 (2026.01.01 ~ 2026.12.31)')
    expect(fiscalEndKo(2025, 1)).toBe('2025년 12월 31일')
  })
  it('3월 결산 — 회계연도 N = N.04.01 ~ N+1.03.31', () => {
    expect(fiscalRange(2026, 4)).toEqual({ start: '2026-04-01', end: '2027-03-31' })
    expect(fyShort(2026, 4)).toBe('2026 회계연도(2026.04~2027.03)')
    expect(fiscalEndKo(2026, 4)).toBe('2027년 3월 31일')
    expect(fiscalYearOfDate(new Date(2027, 2, 15), 4)).toBe(2026)
    expect(fiscalYearOfDate(new Date(2027, 3, 1), 4)).toBe(2027)
  })
  it('6월 결산 말일·윤년', () => {
    expect(fiscalRange(2027, 7).end).toBe('2028-06-30')
    expect(fiscalRange(2027, 3).end).toBe('2028-02-29')
    expect(describeClose(3)).toBe('3월 결산 · 4월 1일 ~ 다음 해 3월 31일')
  })
})
