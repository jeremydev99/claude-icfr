import { describe, expect, it } from 'vitest'
import { decisionCounts, proposerLabel } from './proposals.pure'

describe('proposals', () => {
  it('결정 집계', () => {
    expect(decisionCounts([{ decision: 'pending' }, { decision: 'accepted' }, { decision: 'modified' }, { decision: 'accepted' }]))
      .toEqual({ total: 4, pending: 1, accepted: 2, rejected: 0, modified: 1 })
  })
  it('제안자 표기', () => {
    expect(proposerLabel('system:claude-proposal')).toBe('Claude(AI) 초안')
    expect(proposerLabel('system:seed')).toBe('시스템(seed)')
  })
})
