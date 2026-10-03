import { describe, expect, it } from 'vitest'
import { coverageRate, coverageTone } from './coverage.pure'

describe('coverage', () => {
  it('비율은 내림, 유의 계정 0 이면 0', () => {
    expect(coverageRate({ significant_total: 3, covered: 2 })).toBe(66)
    expect(coverageRate({ significant_total: 0, covered: 0 })).toBe(0)
  })
  it('전부 대응만 ok', () => {
    expect(coverageTone({ significant_total: 4, covered: 4 })).toBe('ok')
    expect(coverageTone({ significant_total: 4, covered: 2 })).toBe('warn')
    expect(coverageTone({ significant_total: 4, covered: 1 })).toBe('bad')
    expect(coverageTone({ significant_total: 0, covered: 0 })).toBe('bad')
  })
})
