import { describe, expect, it } from 'vitest'
import { QUAL_SHORT, qualRuleText } from './qualFactors.pure'

describe('qualFactors', () => {
  it('10개 요소 모두 짧은 이름이 있다', () => {
    expect(Object.keys(QUAL_SHORT)).toHaveLength(10)
  })
  it('기준값·비교 방식이 문장에 들어간다', () => {
    expect(qualRuleText({ threshold: '2', comparison: 'ge' })).toContain('평균이 2 이상')
    expect(qualRuleText({ threshold: '2.00', comparison: 'gt' })).toContain('평균이 2 초과')
  })
})
