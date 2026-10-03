import { describe, expect, it } from 'vitest'
import { approvalSteps, formatValues } from './governance.pure'
import type { GovernanceInfo } from './types'

const base: GovernanceInfo = {
  version: 1, my_tier: 3, my_tier_label: '마스터관리자', review_path: null, requested_by: null, requested_at: null,
  reviewed_by: null, reviewed_at: null, confirmed_by: null, pending_reopen: null, external_approvals: [],
  can: { edit: true, submit: true, withdraw: false, review: false, review_return: false, approve: false,
    external_approve: false, reopen_request: false, reopen_decide: false, reopen_external: false, why: {} },
}

describe('approvalSteps', () => {
  it('일반 작성 → 책임 검토 → 마스터 승인', () => {
    const g = { ...base, review_path: 'lead_then_master' as const, requested_by: { id: '1', name: '김' } }
    expect(approvalSteps('review', g).map((s) => [s.key, s.state])).toEqual([
      ['submit', 'done'], ['review', 'current'], ['approve', 'todo']])
    const g2 = { ...g, reviewed_by: { id: '2', name: '노' } }
    expect(approvalSteps('review', g2).map((s) => s.state)).toEqual(['done', 'done', 'current'])
  })
  it('마스터 작성 → 대표이사·이사회', () => {
    const g = { ...base, review_path: 'external' as const }
    const steps = approvalSteps('confirmed', { ...g, external_approvals: [{ id: 'e', purpose: 'approve',
      approver_body: 'board', approved_on: '2030-03-20', reference: null, recorded_by: null, created_at: '', files: [] }] })
    expect(steps[1]).toMatchObject({ label: '대표이사·이사회 승인', who: '이사회', state: 'done' })
  })
  it('작성 중이면 첫 단계가 현재', () => {
    expect(approvalSteps('draft', base)[0].state).toBe('current')
  })
})

describe('formatValues', () => {
  it('키: 값, 긴 값은 줄임', () => {
    expect(formatValues({ a: 1, b: null })).toBe('a: 1 · b: —')
    expect(formatValues({ a: 'x'.repeat(100) }, 10)).toBe('a: ' + 'x'.repeat(10) + '…')
    expect(formatValues(null)).toBe('')
  })
})
