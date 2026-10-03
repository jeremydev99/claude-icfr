// Report 초안 — 라이브 데이터에서 보고서 준비 상태·운영실태 보고서·감사(위원회) 평가보고서 수치와
// 문구를 산출하는 순수 함수. **화면은 여기서 나온 값만 그린다 — 숫자를 지어내지 않는다.**
//
// 보고서 구조 근거(요약·인용 아님): 주식회사 등의 외부감사에 관한 법률 제8조(대표이사의 운영실태
// 보고, 감사(위원회)의 평가·보고), 내부회계관리제도 평가 및 보고 기준·모범규준.
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

// ── 미비점 분류 ──────────────────────────────────────────────

/** 보고서 상 미비점 등급. 시스템 심각도(높음/중간/낮음)에서 대응시킨다(초안 가정). */
export type DeficiencyClass = 'material_weakness' | 'significant' | 'simple' | 'unclassified'

export const DEFICIENCY_CLASS_ORDER: DeficiencyClass[] = ['material_weakness', 'significant', 'simple', 'unclassified']

export const DEFICIENCY_CLASS_LABEL: Record<DeficiencyClass, string> = {
  material_weakness: '중요한 취약점',
  significant: '유의한 미비점',
  simple: '단순한 미비점',
  unclassified: '분류 전',
}

/** 심각도 코드 → 미비점 등급. 모르는 코드·빈 값은 '분류 전'. */
export function classifyDeficiency(severity: string | null | undefined): DeficiencyClass {
  switch (severity) {
    case 'high': return 'material_weakness'
    case 'medium': return 'significant'
    case 'low': return 'simple'
    default: return 'unclassified'
  }
}

// ── 입력·사실 ────────────────────────────────────────────────

export interface ReportInputs {
  scoping?: ScopingSummary | null
  rcm?: RcmSummary | null
  testRuns?: TestRun[]
  deficiencies?: Deficiency[]
  plans?: RemediationPlan[]
  evidenceTotal?: number
  statements?: StatementListItem[]
}

export interface ClassCount { total: number; open: number }

export interface ReportFacts {
  fiscalYear: number | null
  significantAccounts: number
  unevaluatedAccounts: number
  scopingStatus: string | null
  /** 재무제표 구분별(BS·IS…) 유의 계정 수 — 스코핑 요약 그대로 */
  significantByStatement: { statement: string; significant: number; unevaluated: number }[]
  controlTotal: number
  processTotal: number
  /** 핵심통제 수. RCM 요약에 축이 없으면 null */
  keyControls: number | null
  /** 프로세스별 통제 수(RCM 요약 라벨 그대로) */
  processes: { label: string; count: number }[]
  tests: { total: number; done: number; pass: number; fail: number; na: number; pending: number }
  /** 설계평가(WTT) 기록이 있는 테스트 수 */
  designRecorded: number
  deficiencies: { total: number; high: number; medium: number; low: number; open: number; closed: number }
  byClass: Record<DeficiencyClass, ClassCount>
  /** 미비점 최종 평가(확정)가 끝나지 않은 건수 */
  unconfirmedDeficiencies: number
  plans: { total: number; planned: number; inProgress: number; completed: number; approved: number }
  /** 개선계획이 하나도 없는 미비점 수 */
  deficienciesWithoutPlan: number
  evidenceTotal: number
  finalStatements: number
  /** 원천 데이터가 존재하는지 — false 면 화면에서 0 대신 '—' 를 쓴다 */
  has: { scoping: boolean; rcm: boolean; tests: boolean; deficiencies: boolean; plans: boolean; evidence: boolean }
}

/** 평가 기준연도: 스코핑 연도 → 테스트·미비점 최신 연도. */
export function pickFiscalYear(i: ReportInputs): number | null {
  if (i.scoping?.exists && i.scoping.fiscal_year) return i.scoping.fiscal_year
  const years = [...(i.testRuns ?? []).map((t) => t.fiscal_year), ...(i.deficiencies ?? []).map((d) => d.fiscal_year)]
  return years.length ? Math.max(...years) : null
}

/** 평가 기준일(회계연도 말). 12월 결산 가정 — 결산월 설정이 생기면 바꾼다. */
export function evaluationDate(fy: number | null): string | null {
  return fy ? `${fy}-12-31` : null
}

const emptyClasses = (): Record<DeficiencyClass, ClassCount> => ({
  material_weakness: { total: 0, open: 0 },
  significant: { total: 0, open: 0 },
  simple: { total: 0, open: 0 },
  unclassified: { total: 0, open: 0 },
})

export function computeFacts(i: ReportInputs): ReportFacts {
  const fy = pickFiscalYear(i)
  const inYear = <T extends { fiscal_year: number }>(xs: T[] | undefined) =>
    (xs ?? []).filter((x) => fy === null || x.fiscal_year === fy)

  let sig = 0
  let unev = 0
  const byStatement: ReportFacts['significantByStatement'] = []
  if (i.scoping?.exists) {
    for (const [statement, s] of Object.entries(i.scoping.by_statement)) {
      sig += s.Y
      unev += s.unevaluated
      byStatement.push({ statement, significant: s.Y, unevaluated: s.unevaluated })
    }
  }

  const runs = inYear(i.testRuns)
  const done = runs.filter((r) => r.status === 'completed' || r.status === 'approved')
  const defs = inYear(i.deficiencies)
  const defIds = new Set(defs.map((d) => d.id))
  const plans = (i.plans ?? []).filter((p) => fy === null || defIds.has(p.deficiency_id))
  const plannedDefs = new Set(plans.map((p) => p.deficiency_id))

  const byClass = emptyClasses()
  for (const d of defs) {
    const c = byClass[classifyDeficiency(d.severity)]
    c.total += 1
    if (d.status !== 'closed') c.open += 1
  }

  const keyGroup = i.rcm?.groups?.find((g) => g.key === 'is_key_control')
  const keyBucket = keyGroup?.buckets.find((b) => b.value === 'True')
  const processGroup = i.rcm?.groups?.find((g) => g.key === 'process')

  const controlTotal = i.rcm?.control_total ?? 0

  return {
    fiscalYear: fy,
    significantAccounts: sig,
    unevaluatedAccounts: unev,
    scopingStatus: i.scoping?.exists ? i.scoping.status : null,
    significantByStatement: byStatement,
    controlTotal,
    processTotal: i.rcm?.process_total ?? 0,
    keyControls: keyGroup ? (keyBucket?.count ?? 0) : null,
    processes: (processGroup?.buckets ?? []).filter((b) => b.count > 0).map((b) => ({ label: b.label, count: b.count })),
    tests: {
      total: runs.length,
      done: done.length,
      pass: runs.filter((r) => r.result === 'pass').length,
      fail: runs.filter((r) => r.result === 'fail').length,
      na: runs.filter((r) => r.result === 'n/a').length,
      pending: runs.length - done.length,
    },
    designRecorded: runs.filter((r) => (r.wtt_summary ?? '').trim() !== '').length,
    deficiencies: {
      total: defs.length,
      high: defs.filter((d) => d.severity === 'high').length,
      medium: defs.filter((d) => d.severity === 'medium').length,
      low: defs.filter((d) => d.severity === 'low').length,
      open: defs.filter((d) => d.status !== 'closed').length,
      closed: defs.filter((d) => d.status === 'closed').length,
    },
    byClass,
    unconfirmedDeficiencies: defs.filter((d) => !d.confirmed_at).length,
    plans: {
      total: plans.length,
      planned: plans.filter((p) => p.status === 'planned').length,
      inProgress: plans.filter((p) => p.status === 'in_progress').length,
      completed: plans.filter((p) => p.status === 'completed').length,
      approved: plans.filter((p) => p.status === 'approved').length,
    },
    deficienciesWithoutPlan: defs.filter((d) => !plannedDefs.has(d.id)).length,
    evidenceTotal: i.evidenceTotal ?? 0,
    finalStatements: (i.statements ?? []).filter((s) => s.status === 'final' && (fy === null || s.fiscal_year === fy)).length,
    has: {
      scoping: sig + unev > 0,
      rcm: controlTotal > 0,
      tests: runs.length > 0,
      // 미비점 0건은 테스트가 있을 때만 "0건"이라는 사실이 된다. 테스트도 없으면 아직 모르는 것.
      deficiencies: i.deficiencies !== undefined && (defs.length > 0 || runs.length > 0),
      plans: i.plans !== undefined && (plans.length > 0 || defs.length > 0),
      evidence: (i.evidenceTotal ?? 0) > 0,
    },
  }
}

// ── 표시 도우미 ──────────────────────────────────────────────

export const DASH = '—'

/** 원천이 없으면 '—', 있으면 숫자(천 단위 구분). null 값도 '—'. */
export function display(value: number | null | undefined, available = true): string {
  if (!available || value === null || value === undefined) return DASH
  return value.toLocaleString('ko-KR')
}

/** 데이터가 없을 때 어느 메뉴에서 채우는지 알려주는 문구. */
export const MISSING_HINT = {
  scoping: '스코핑 확정 후 표시',
  rcm: 'RCM 등록 후 표시',
  tests: '테스트 수행 후 표시',
  deficiencies: '테스트 결과·미비점 등록 후 표시',
  plans: '미비점별 개선계획 등록 후 표시',
  evidence: '증빙 업로드 후 표시',
  fiscalYear: '스코핑 또는 테스트 회차 생성 후 표시',
  controlType: 'RCM에 통제 유형(전사적 통제·IT일반통제) 분류 항목이 없어 집계 불가',
} as const

// ── 결론 문안 선택 ───────────────────────────────────────────

export type ConclusionKind = 'insufficient' | 'ineffective' | 'effective'

export interface Conclusion {
  kind: ConclusionKind
  /** 보고서 본문에 들어갈 초안 문장 */
  text: string
  /** 결론 확정 전 확인할 사항(보고서 밖 메모) */
  caveats: string[]
}

export const CONCLUSION_BASIS = '근거: 내부회계관리제도 평가 및 보고 기준(평가 및 보고 모범규준)'
export const CONCLUSION_DRAFT_NOTE = '초안 문구 — 최종 문안은 내부회계관리자가 확정'

function conclusionCaveats(f: ReportFacts): string[] {
  const c: string[] = []
  if (f.tests.pending > 0) c.push(`미완료 테스트 ${f.tests.pending}건이 결과에 반영되지 않았습니다.`)
  if (f.unconfirmedDeficiencies > 0) c.push(`최종 평가가 확정되지 않은 미비점 ${f.unconfirmedDeficiencies}건이 있습니다.`)
  if (f.byClass.unclassified.total > 0) c.push(`등급이 분류되지 않은 미비점 ${f.byClass.unclassified.total}건이 있습니다.`)
  const closedMw = f.byClass.material_weakness.total - f.byClass.material_weakness.open
  if (closedMw > 0) c.push(`기중 개선 완료된 중요한 취약점 ${closedMw}건 — 기말 재테스트로 개선 효과를 확인해야 결론에서 제외할 수 있습니다.`)
  if (f.unevaluatedAccounts > 0) c.push(`스코핑 미평가 계정 ${f.unevaluatedAccounts}개가 있어 평가 범위가 확정되지 않았습니다.`)
  return c
}

/**
 * 운영실태 보고서 결론 초안.
 * - 테스트가 없으면 결론을 만들지 않는다.
 * - 미종결 중요한 취약점이 1건이라도 있으면 '효과적이지 않다'.
 * - 그 외에는 '효과적이다'(유의한 미비점은 결론을 바꾸지 않되 본문 Ⅳ에서 공시).
 */
export function selectConclusion(f: ReportFacts): Conclusion {
  const caveats = conclusionCaveats(f)
  const date = evaluationDate(f.fiscalYear)
  const asOf = date ? `${date.slice(0, 4)}년 ${Number(date.slice(5, 7))}월 ${Number(date.slice(8, 10))}일 현재` : '평가 기준일 현재'
  if (f.tests.total === 0) {
    return { kind: 'insufficient', text: '설계 및 운영 평가 결과가 없어 결론 문안을 만들 수 없습니다.', caveats }
  }
  const mw = f.byClass.material_weakness.open
  if (mw > 0) {
    return {
      kind: 'ineffective',
      text: `${asOf} 회사의 내부회계관리제도는 중요한 취약점 ${mw}건으로 인하여, 내부회계관리제도 설계 및 운영 개념체계에 비추어 볼 때 중요성의 관점에서 효과적으로 설계 및 운영되고 있지 않다고 판단합니다.`,
      caveats,
    }
  }
  return {
    kind: 'effective',
    text: `${asOf} 회사의 내부회계관리제도는 내부회계관리제도 설계 및 운영 개념체계에 비추어 볼 때 중요성의 관점에서 효과적으로 설계 및 운영되고 있다고 판단합니다.`,
    caveats,
  }
}

/** 감사(위원회) 평가보고서 결론 초안 — 운영실태 결론을 감사(위원회)의 관점으로 바꾼다. */
export function selectAuditCommitteeConclusion(f: ReportFacts): Conclusion {
  const base = selectConclusion(f)
  if (base.kind === 'insufficient') {
    return { ...base, text: '대표이사의 운영실태 보고 근거가 되는 평가 결과가 없어 평가 의견 문안을 만들 수 없습니다.' }
  }
  const text = base.kind === 'ineffective'
    ? `감사(위원회)는 대표이사가 보고한 내부회계관리제도 운영실태를 검토한 결과, 중요한 취약점 ${f.byClass.material_weakness.open}건으로 인하여 회사의 내부회계관리제도가 중요성의 관점에서 효과적으로 설계 및 운영되고 있지 않다고 판단합니다.`
    : '감사(위원회)는 대표이사가 보고한 내부회계관리제도 운영실태를 검토한 결과, 회사의 내부회계관리제도가 중요성의 관점에서 효과적으로 설계 및 운영되고 있다고 판단합니다.'
  const caveats = [...base.caveats]
  if (f.deficienciesWithoutPlan > 0) caveats.push(`개선계획이 없는 미비점 ${f.deficienciesWithoutPlan}건 — 시정 계획의 적정성 검토 대상입니다.`)
  return { kind: base.kind, text, caveats }
}

// ── 준비 상태 카드 ───────────────────────────────────────────

export interface ReportCardDef {
  id: string
  title: string
  /** 법정 보고서(true) / 보조 산출물(false) */
  statutory: boolean
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
  const defsHandled = f.tests.total > 0 && f.deficienciesWithoutPlan === 0
  // 등급 분류·최종 평가가 끝났는지 — 테스트가 없으면 판단할 것도 없다
  const defsClassified = f.tests.total > 0 && f.byClass.unclassified.total === 0 && f.unconfirmedDeficiencies === 0
  return [
    {
      id: 'ops-report',
      title: '내부회계관리제도 운영실태 보고서',
      statutory: true,
      audience: '대표이사 → 이사회·감사(위원회)',
      contents: ['개요·평가 기준', '평가 범위', '설계·운영 평가 결과', '미비점 현황', '결론', '서명'],
      sources: ['스코핑', 'RCM', '테스트', '미비점·개선계획'],
      readiness: readinessOf([f.significantAccounts > 0, f.controlTotal > 0, testsDone, defsHandled, defsClassified]),
      note: testsDone ? '테스트 완료' : `테스트 ${f.tests.done}/${f.tests.total} 완료`,
    },
    {
      id: 'audit-committee',
      title: '감사(위원회)의 내부회계관리제도 평가보고서',
      statutory: true,
      audience: '감사(위원회) → 이사회',
      contents: ['평가 대상 기간', '평가 방법', '평가 결론', '서명'],
      sources: ['운영실태 보고서', '미비점·개선계획'],
      readiness: readinessOf([testsDone, defsHandled, f.tests.total > 0 && f.plans.total === f.plans.approved]),
      note: '운영실태 보고서 확정 후 작성',
    },
    {
      id: 'scoping',
      title: '스코핑 결과',
      statutory: false,
      audience: '내부회계관리자·외부감사인',
      contents: ['중요성 기준', '유의한 계정·공시', '유의 프로세스 매핑'],
      sources: ['스코핑', '재무제표'],
      readiness: readinessOf([f.significantAccounts > 0, scopingDone, f.finalStatements > 0]),
      note: f.unevaluatedAccounts > 0 ? `미평가 계정 ${f.unevaluatedAccounts}개` : `유의 계정 ${f.significantAccounts}개`,
    },
    {
      id: 'rcm',
      title: 'RCM (위험통제기술서)',
      statutory: false,
      audience: '내부회계관리자·외부감사인',
      contents: ['프로세스별 통제', '핵심통제 지정', '통제 속성'],
      sources: ['RCM'],
      readiness: readinessOf([f.controlTotal > 0, f.processTotal > 0, (f.keyControls ?? 0) > 0]),
      note: `프로세스 ${f.processTotal} · 통제 ${f.controlTotal}${f.keyControls !== null ? ` · 핵심 ${f.keyControls}` : ''}`,
    },
    {
      id: 'test-workpapers',
      title: '테스트 조서',
      statutory: false,
      audience: '내부회계관리자·외부감사인',
      contents: ['설계평가(WTT)', '운영평가 결과', '표본·절차', '증빙'],
      sources: ['테스트', '증빙'],
      readiness: readinessOf([f.tests.total > 0, testsDone, f.evidenceTotal > 0]),
      note: `테스트 완료 ${f.tests.done}/${f.tests.total} · 증빙 ${f.evidenceTotal}`,
    },
    {
      id: 'deficiency',
      title: '미비점 목록·개선계획',
      statutory: false,
      audience: '내부회계관리자·감사(위원회)',
      contents: ['등급별 미비점', '최종 평가 확정', '개선계획 진행'],
      sources: ['미비점', '개선계획'],
      readiness: readinessOf([f.tests.total > 0, defsHandled, defsClassified]),
      note: `미비점 ${f.deficiencies.total}건 · 개선계획 ${f.plans.total}건`,
    },
  ]
}
