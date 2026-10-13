import { describe, expect, it } from 'vitest'
import { QUAL_SHORT, qualRuleText, ratingsSummary } from './qualFactors.pure'

describe('qualFactors', () => {
  it('10개 요소 모두 짧은 이름이 있다', () => {
    expect(Object.keys(QUAL_SHORT)).toHaveLength(10)
  })
  it('기준값·비교 방식이 문장에 들어간다', () => {
    expect(qualRuleText({ threshold: '2', comparison: 'ge' })).toContain('평균이 2 이상')
    expect(qualRuleText({ threshold: '2.00', comparison: 'gt' })).toContain('평균이 2 초과')
  })
})

describe('ratingsSummary', () => {
  it('요소 순서대로 등급, 빈칸은 ·', () => {
    expect(ratingsSummary({ a: 'H', c: 'L' }, ['a', 'b', 'c'])).toEqual({ text: 'H·L', filled: 2, total: 3 })
    expect(ratingsSummary({}, ['a', 'b'])).toEqual({ text: '··', filled: 0, total: 2 })
    expect(ratingsSummary({ a: null, b: '' }, ['a', 'b']).filled).toBe(0)
  })
})
