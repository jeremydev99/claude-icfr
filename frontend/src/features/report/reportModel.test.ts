// @vitest-environment node
import { describe, it, expect } from 'vitest'
import { buildReportCards, computeFacts, readinessOf } from './reportModel'
import type { TestRun } from '@/features/test/types'
import type { Deficiency, RemediationPlan } from '@/features/remediation/types'

const run = (p: Partial<TestRun>) => ({ fiscal_year: 2026, status: 'planned', result: null, ...p }) as TestRun
const def = (p: Partial<Deficiency>) => ({ fiscal_year: 2026, severity: 'low', status: 'open', ...p }) as Deficiency

describe('readinessOf', () => {
  it('전부/일부/없음', () => {
    expect(readinessOf([true, true])).toBe('ready')
    expect(readinessOf([true, false])).toBe('partial')
    expect(readinessOf([false])).toBe('empty')
    expect(readinessOf([])).toBe('empty')
  })
})

describe('computeFacts', () => {
  it('빈 입력은 0·연도 null·카드 전부 데이터 없음', () => {
    const f = computeFacts({})
    expect(f.fiscalYear).toBeNull()
    expect(f.tests.total).toBe(0)
    expect(buildReportCards(f).every((c) => c.readiness === 'empty')).toBe(true)
  })

  it('스코핑 연도로 필터하고 결과·심각도를 센다', () => {
    const f = computeFacts({
      scoping: {
        exists: true, fiscal_year: 2026, status: 'draft', overall_materiality: 1, smt: 1, badge_count: 0,
        by_statement: { BS: { Y: 3, N: 2, unevaluated: 1 }, IS: { Y: 2, N: 0, unevaluated: 0 } },
      },
      testRuns: [
        run({ status: 'approved', result: 'pass' }),
        run({ status: 'completed', result: 'fail' }),
        run({}),
        run({ fiscal_year: 2025, result: 'pass' }),
      ],
      deficiencies: [def({ id: 'd1', severity: 'high' }), def({ id: 'd2', status: 'closed' }), def({ id: 'd3', fiscal_year: 2025 })],
      plans: [
        { deficiency_id: 'd1', status: 'approved' } as RemediationPlan,
        { deficiency_id: 'd3', status: 'planned' } as RemediationPlan,
      ],
    })
    expect(f.fiscalYear).toBe(2026)
    expect(f.significantAccounts).toBe(5)
    expect(f.unevaluatedAccounts).toBe(1)
    expect(f.tests).toEqual({ total: 3, done: 2, pass: 1, fail: 1, na: 0, pending: 1 })
    expect(f.deficiencies).toMatchObject({ total: 2, high: 1, low: 1, open: 1, closed: 1 })
    expect(f.plans).toMatchObject({ total: 1, approved: 1 })
    const scoping = buildReportCards(f).find((c) => c.id === 'scoping')!
    expect(scoping.readiness).toBe('partial')
  })
})
