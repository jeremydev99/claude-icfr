import { describe, expect, it } from 'vitest'
import { createdNotice, periodIndexOptions, periodLabel, suggestCycleName } from './cycle.pure'

describe('periodIndexOptions', () => {
  it('주기별 차수 개수', () => {
    expect(periodIndexOptions('annual')).toEqual([1])
    expect(periodIndexOptions('semiannual')).toEqual([1, 2])
    expect(periodIndexOptions('quarterly')).toHaveLength(4)
    expect(periodIndexOptions('monthly')).toHaveLength(12)
    expect(periodIndexOptions('weekly')).toHaveLength(53)
  })
  it('모르는 주기는 1개', () => {
    expect(periodIndexOptions('daily')).toEqual([1])
  })
})

describe('periodLabel', () => {
  it('반기·분기·주', () => {
    expect(periodLabel('semiannual', 1)).toBe('상반기')
    expect(periodLabel('semiannual', 2)).toBe('하반기')
    expect(periodLabel('quarterly', 3)).toBe('3분기')
    expect(periodLabel('weekly', 7)).toBe('7주차')
  })
  it('월별은 기간 시작월 기준 — 회계연도 4월 시작이면 1차수는 4월', () => {
    expect(periodLabel('monthly', 1, '2026-04-01')).toBe('4월')
  })
  it('월별 시작일을 모르면 차수로', () => {
    expect(periodLabel('monthly', 2)).toBe('2차')
  })
})

describe('suggestCycleName', () => {
  it('연도·차수·종류', () => {
    expect(suggestCycleName(2026, 'operation', 'quarterly', 3)).toBe('2026 3분기 운영평가')
    expect(suggestCycleName(2026, 'design', 'annual', 1)).toBe('2026 연간 설계평가')
  })
})

describe('createdNotice', () => {
  it('대상 0건·null 은 경고', () => {
    expect(createdNotice(0).tone).toBe('warn')
    expect(createdNotice(null).tone).toBe('warn')
  })
  it('대상 있으면 건수 안내', () => {
    expect(createdNotice(5)).toEqual({ tone: 'ok', text: expect.stringContaining('5건') })
  })
})
