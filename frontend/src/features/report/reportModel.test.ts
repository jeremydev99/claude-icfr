// @vitest-environment node
import { describe, it, expect } from 'vitest'
import {
  DASH, DEFICIENCY_CLASS_LABEL, buildReportCards, classifyDeficiency, computeFacts, display, evaluationDate,
  readinessOf, selectAuditCommitteeConclusion, selectConclusion,
} from './reportModel'
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

describe('classifyDeficiency', () => {
  it('심각도 코드 → 미비점 등급, 모르는 값은 분류 전', () => {
    expect(classifyDeficiency('high')).toBe('material_weakness')
    expect(classifyDeficiency('medium')).toBe('significant')
    expect(classifyDeficiency('low')).toBe('simple')
    expect(classifyDeficiency('critical')).toBe('unclassified')
    expect(classifyDeficiency(null)).toBe('unclassified')
    expect(classifyDeficiency(undefined)).toBe('unclassified')
    expect(DEFICIENCY_CLASS_LABEL.unclassified).toBe('분류 전')
  })

  it('computeFacts 가 등급별 발견·미종결을 센다', () => {
    const f = computeFacts({
      testRuns: [run({ status: 'completed', result: 'fail' })],
      deficiencies: [
        def({ id: 'a', severity: 'high' }),
        def({ id: 'b', severity: 'high', status: 'closed' }),
        def({ id: 'c', severity: 'medium' }),
        def({ id: 'd', severity: 'weird' as Deficiency['severity'] }),
      ],
      plans: [{ deficiency_id: 'a', status: 'planned' } as RemediationPlan],
    })
    expect(f.byClass.material_weakness).toEqual({ total: 2, open: 1 })
    expect(f.byClass.significant).toEqual({ total: 1, open: 1 })
    expect(f.byClass.simple).toEqual({ total: 0, open: 0 })
    expect(f.byClass.unclassified).toEqual({ total: 1, open: 1 })
    expect(f.deficienciesWithoutPlan).toBe(3)
    expect(f.unconfirmedDeficiencies).toBe(4)
  })
})

describe('display / has (— 처리)', () => {
  it('원천이 없거나 null 이면 —, 있으면 숫자', () => {
    expect(display(0, false)).toBe(DASH)
    expect(display(null)).toBe(DASH)
    expect(display(undefined)).toBe(DASH)
    expect(display(0)).toBe('0')
    expect(display(1234)).toBe('1,234')
  })

  it('빈 입력은 모든 원천이 없음', () => {
    const f = computeFacts({})
    expect(f.has).toEqual({ scoping: false, rcm: false, tests: false, deficiencies: false, plans: false, evidence: false })
    expect(f.keyControls).toBeNull()
  })

  it('미비점 0건은 테스트가 있을 때만 사실(0)로 본다', () => {
    expect(computeFacts({ deficiencies: [] }).has.deficiencies).toBe(false)
    expect(computeFacts({ deficiencies: [], testRuns: [run({})] }).has.deficiencies).toBe(true)
  })

  it('RCM 요약에서 핵심통제·프로세스를 읽는다', () => {
    const f = computeFacts({
      rcm: {
        control_total: 10, process_total: 2,
        groups: [
          { key: 'is_key_control', label: '', filter_param: null, buckets: [{ value: 'True', label: '핵심', count: 7 }, { value: 'False', label: '비핵심', count: 3 }] },
          { key: 'process', label: '', filter_param: null, buckets: [{ value: 'P1', label: 'P1 매출', count: 6 }, { value: 'P2', label: 'P2 구매', count: 0 }] },
        ],
        org: { unassigned: 0, buckets: [] },
        progress: { cycles: 0, targets: 0, activities: 0, completed: 0, incomplete: 0 },
      },
    })
    expect(f.has.rcm).toBe(true)
    expect(f.keyControls).toBe(7)
    expect(f.processes).toEqual([{ label: 'P1 매출', count: 6 }])
  })
})

describe('evaluationDate', () => {
  it('회계연도 말(12월 결산 가정)', () => {
    expect(evaluationDate(2026)).toBe('2026-12-31')
    expect(evaluationDate(null)).toBeNull()
  })
})

describe('selectConclusion', () => {
  it('테스트가 없으면 결론 불가', () => {
    expect(selectConclusion(computeFacts({})).kind).toBe('insufficient')
    expect(selectAuditCommitteeConclusion(computeFacts({})).kind).toBe('insufficient')
  })

  it('미종결 중요한 취약점이 있으면 효과적이지 않다', () => {
    const f = computeFacts({
      testRuns: [run({ status: 'completed', result: 'fail' })],
      deficiencies: [def({ id: 'a', severity: 'high' })],
    })
    const c = selectConclusion(f)
    expect(c.kind).toBe('ineffective')
    expect(c.text).toContain('효과적으로 설계 및 운영되고 있지 않다')
    expect(c.text).toContain('2026년 12월 31일 현재')
    expect(selectAuditCommitteeConclusion(f).kind).toBe('ineffective')
    expect(selectAuditCommitteeConclusion(f).caveats.some((t) => t.includes('개선계획이 없는 미비점 1건'))).toBe(true)
  })

  it('유의한 미비점만 있거나 중요한 취약점이 종결되면 효과적 + 확인 사항', () => {
    const f = computeFacts({
      testRuns: [run({ status: 'approved', result: 'pass' }), run({})],
      deficiencies: [
        def({ id: 'a', severity: 'medium', confirmed_at: '2026-11-01' }),
        def({ id: 'b', severity: 'high', status: 'closed', confirmed_at: '2026-11-01' }),
      ],
    })
    const c = selectConclusion(f)
    expect(c.kind).toBe('effective')
    expect(c.text).toContain('효과적으로 설계 및 운영되고 있다고')
    expect(c.caveats.some((t) => t.includes('미완료 테스트 1건'))).toBe(true)
    expect(c.caveats.some((t) => t.includes('기중 개선 완료된 중요한 취약점 1건'))).toBe(true)
  })
})

describe('buildReportCards', () => {
  it('법정 보고서 2종 + 보조 산출물 4종', () => {
    const cards = buildReportCards(computeFacts({}))
    expect(cards.map((c) => c.id)).toEqual(['ops-report', 'audit-committee', 'scoping', 'rcm', 'test-workpapers', 'deficiency'])
    expect(cards.filter((c) => c.statutory)).toHaveLength(2)
  })

  it('분류 전 미비점이 있으면 운영실태 보고서는 준비됨이 아니다', () => {
    const base = {
      scoping: { exists: true, fiscal_year: 2026, status: 'final', overall_materiality: 1, smt: 1, badge_count: 0, by_statement: { BS: { Y: 1, N: 0, unevaluated: 0 } } },
      rcm: { control_total: 1, process_total: 1, groups: [], org: { unassigned: 0, buckets: [] }, progress: { cycles: 0, targets: 0, activities: 0, completed: 0, incomplete: 0 } },
      testRuns: [run({ status: 'approved', result: 'pass' })],
      plans: [{ deficiency_id: 'a', status: 'approved' } as RemediationPlan],
    }
    const ok = computeFacts({ ...base, deficiencies: [def({ id: 'a', confirmed_at: '2026-11-01' })] })
    expect(buildReportCards(ok)[0].readiness).toBe('ready')
    const bad = computeFacts({ ...base, deficiencies: [def({ id: 'a', confirmed_at: null, severity: 'x' as Deficiency['severity'] })] })
    expect(buildReportCards(bad)[0].readiness).toBe('partial')
  })
})
