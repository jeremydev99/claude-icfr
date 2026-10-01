// Report 초안 — 라이브 데이터에서 보고서 준비 상태·운영실태 보고서 개요 수치를 산출하는 순수 함수.
import type { ScopingSummary } from '@/features/scoping/types'
import type { RcmSummary } from '@/features/dashboard/api/types'
import type { TestRun } from '@/features/test/types'
import type { Deficiency, RemediationPlan } from '@/features/remediation/types'
import type { StatementListItem } from '@/features/financial-statements/types'

export type Readiness = 'ready' | 'partial' | 'empty'

export const READINESS_LABEL: Record<Readiness, string> = {
  ready: '준비됨',
  partial: '부분',
  empty: '데이터 없음',
}

/** 조건 목록 → 전부 충족이면 준비됨, 일부면 부분, 없으면 데이터 없음. */
export function readinessOf(checks: boolean[]): Readiness {
  const n = checks.filter(Boolean).length
  if (checks.length > 0 && n === checks.length) return 'ready'
  return n > 0 ? 'partial' : 'empty'
}

export interface ReportInputs {
  scoping?: ScopingSummary | null
  rcm?: RcmSummary | null
  testRuns?: TestRun[]
  deficiencies?: Deficiency[]
  plans?: RemediationPlan[]
  evidenceTotal?: number
  statements?: StatementListItem[]
}

export interface ReportFacts {
  fiscalYear: number | null
  significantAccounts: number
  unevaluatedAccounts: number
  scopingStatus: string | null
  controlTotal: number
  processTotal: number
  tests: { total: number; done: number; pass: number; fail: number; na: number; pending: number }
  deficiencies: { total: number; high: number; medium: number; low: number; open: number; closed: number }
  plans: { total: number; planned: number; inProgress: number; completed: number; approved: number }
  evidenceTotal: number
  finalStatements: number
}

/** 평가 기준연도: 스코핑 연도 → 테스트·미비점 최신 연도. */
export function pickFiscalYear(i: ReportInputs): number | null {
  if (i.scoping?.exists && i.scoping.fiscal_year) return i.scoping.fiscal_year
  const years = [...(i.testRuns ?? []).map((t) => t.fiscal_year), ...(i.deficiencies ?? []).map((d) => d.fiscal_year)]
  return years.length ? Math.max(...years) : null
}

export function computeFacts(i: ReportInputs): ReportFacts {
  const fy = pickFiscalYear(i)
  const inYear = <T extends { fiscal_year: number }>(xs: T[] | undefined) =>
    (xs ?? []).filter((x) => fy === null || x.fiscal_year === fy)

  let sig = 0
  let unev = 0
  if (i.scoping?.exists) {
    for (const s of Object.values(i.scoping.by_statement)) { sig += s.Y; unev += s.unevaluated }
  }

  const runs = inYear(i.testRuns)
  const done = runs.filter((r) => r.status === 'completed' || r.status === 'approved')
  const defs = inYear(i.deficiencies)
  const defIds = new Set(defs.map((d) => d.id))
  const plans = (i.plans ?? []).filter((p) => fy === null || defIds.has(p.deficiency_id))

  return {
    fiscalYear: fy,
    significantAccounts: sig,
    unevaluatedAccounts: unev,
    scopingStatus: i.scoping?.exists ? i.scoping.status : null,
    controlTotal: i.rcm?.control_total ?? 0,
    processTotal: i.rcm?.process_total ?? 0,
    tests: {
      total: runs.length,
      done: done.length,
      pass: runs.filter((r) => r.result === 'pass').length,
      fail: runs.filter((r) => r.result === 'fail').length,
      na: runs.filter((r) => r.result === 'n/a').length,
      pending: runs.length - done.length,
    },
    deficiencies: {
      total: defs.length,
      high: defs.filter((d) => d.severity === 'high').length,
      medium: defs.filter((d) => d.severity === 'medium').length,
      low: defs.filter((d) => d.severity === 'low').length,
      open: defs.filter((d) => d.status !== 'closed').length,
      closed: defs.filter((d) => d.status === 'closed').length,
    },
    plans: {
      total: plans.length,
      planned: plans.filter((p) => p.status === 'planned').length,
      inProgress: plans.filter((p) => p.status === 'in_progress').length,
      completed: plans.filter((p) => p.status === 'completed').length,
      approved: plans.filter((p) => p.status === 'approved').length,
    },
    evidenceTotal: i.evidenceTotal ?? 0,
    finalStatements: (i.statements ?? []).filter((s) => s.status === 'final' && (fy === null || s.fiscal_year === fy)).length,
  }
}

export interface ReportCardDef {
  id: string
  title: string
  audience: string
  contents: string[]
  sources: string[]
  readiness: Readiness
  note: string
}

export function buildReportCards(f: ReportFacts): ReportCardDef[] {
  const scopingDone = f.significantAccounts > 0 && f.unevaluatedAccounts === 0
  const testsDone = f.tests.total > 0 && f.tests.pending === 0
  // 미비점마다 개선계획이 있어야 "처리됨" (미비점이 없으면 테스트가 있어야 의미가 있다)
  const defsHandled = f.tests.total > 0 && f.deficiencies.total <= f.plans.total
  return [
    {
      id: 'ops-report',
      title: '내부회계관리제도 운영실태 보고서',
      audience: '대표이사 → 이사회·감사(위원회)',
      contents: ['평가 기준연도·범위', '설계·운영 평가 결과', '미비점 및 개선계획', '운영실태 결론'],
      sources: ['스코핑', 'RCM', '테스트', '미비점·개선계획'],
      readiness: readinessOf([f.significantAccounts > 0, f.controlTotal > 0, testsDone, defsHandled]),
      note: testsDone ? '테스트 완료' : `테스트 ${f.tests.done}/${f.tests.total} 완료`,
    },
    {
      id: 'audit-committee',
      title: '감사(위원회) 운영실태 평가보고서',
      audience: '감사(위원회) → 이사회·정기주주총회',
      contents: ['운영실태 보고서 검토 결과', '평가 절차·범위의 적정성', '미비점 시정조치 적정성', '평가 의견'],
      sources: ['운영실태 보고서', '미비점·개선계획'],
      readiness: readinessOf([testsDone, defsHandled, f.tests.total > 0 && f.plans.total === f.plans.approved]),
      note: '운영실태 보고서 확정 후 작성',
    },
    {
      id: 'scoping',
      title: '스코핑 결과 요약',
      audience: '내부회계관리자·외부감사인',
      contents: ['중요성 기준', '유의한 계정·공시', '유의 프로세스 매핑'],
      sources: ['스코핑', '재무제표'],
      readiness: readinessOf([f.significantAccounts > 0, scopingDone, f.finalStatements > 0]),
      note: f.unevaluatedAccounts > 0 ? `미평가 계정 ${f.unevaluatedAccounts}개` : `유의 계정 ${f.significantAccounts}개`,
    },
    {
      id: 'deficiency',
      title: '미비점·개선계획 현황',
      audience: '내부회계관리자·감사(위원회)',
      contents: ['심각도별 미비점', '개선계획 진행 상태', '재테스트 결과'],
      sources: ['미비점', '개선계획'],
      readiness: readinessOf([f.tests.total > 0, defsHandled]),
      note: `미비점 ${f.deficiencies.total}건 · 개선계획 ${f.plans.total}건`,
    },
    {
      id: 'pbc',
      title: '외부감사인 제출 패키지 (PBC)',
      audience: '외부감사인',
      contents: ['RCM', '테스트 결과', '증빙 목록', '미비점 평가'],
      sources: ['RCM', '테스트', '증빙'],
      readiness: readinessOf([f.controlTotal > 0, f.tests.done > 0, f.evidenceTotal > 0]),
      note: `통제 ${f.controlTotal} · 테스트 완료 ${f.tests.done} · 증빙 ${f.evidenceTotal}`,
    },
  ]
}
