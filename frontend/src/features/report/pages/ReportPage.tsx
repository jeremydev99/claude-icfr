import { useMemo, useRef } from 'react'
import { Printer } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { useScopingMeta, useScopingSummary } from '@/features/scoping/api/useScoping'
import { useRcmSummary } from '@/features/dashboard/api/useRcmSummary'
import { useTestRuns } from '@/features/test/api/useTestRuns'
import { useDeficiencies } from '@/features/remediation/api/useDeficiencies'
import { usePlans } from '@/features/remediation/api/useRemediationPlans'
import { useEvidenceFiles } from '@/features/evidence/api/useEvidence'
import { useFsStatements } from '@/features/financial-statements/api/useFs'
import {
  READINESS_LABEL, buildReportCards, computeFacts, type ReportFacts, type Readiness,
} from '../reportModel'

// 초안: 전용 집계 API가 없어 목록 API를 넉넉한 limit 으로 받아 화면에서 센다.
const ALL = { limit: 1000 }

const READINESS_STYLE: Record<Readiness, string> = {
  ready: 'border-emerald-300 bg-emerald-50 text-emerald-900',
  partial: 'border-amber-300 bg-amber-50 text-amber-900',
  empty: 'border-slate-300 bg-slate-50 text-slate-600',
}

export default function ReportPage() {
  const scoping = useScopingSummary()
  const { data: scopingMeta } = useScopingMeta()
  const rcm = useRcmSummary()
  const tests = useTestRuns(ALL)
  const defs = useDeficiencies(ALL)
  const plans = usePlans(ALL)
  const evidence = useEvidenceFiles({ limit: 1 })
  const statements = useFsStatements()

  const loading = [scoping, rcm, tests, defs, plans, evidence, statements].some((q) => q.isLoading)
  const failed = [scoping, rcm, tests, defs, plans, evidence, statements].filter((q) => q.isError).length

  const facts = useMemo(() => computeFacts({
    scoping: scoping.data,
    rcm: rcm.data,
    testRuns: tests.data?.items,
    deficiencies: defs.data?.items,
    plans: plans.data?.items,
    evidenceTotal: evidence.data?.total,
    statements: statements.data,
  }), [scoping.data, rcm.data, tests.data, defs.data, plans.data, evidence.data, statements.data])
  const cards = useMemo(() => buildReportCards(facts), [facts])
  const scopingStatusLabel = scopingMeta?.statuses.find((s) => s.value === facts.scopingStatus)?.label ?? facts.scopingStatus

  return (
    <div className="space-y-4 p-6">
      <div className="flex flex-wrap items-center gap-2">
        <h1 className="text-2xl font-bold">Report</h1>
        <Badge variant="outline" className="border-amber-300 bg-amber-50 text-amber-900">
          초안 — 보고서 양식(운영 양식과 맞춰 조정 예정)
        </Badge>
      </div>
      <p className="text-sm text-muted-foreground">
        내부회계관리제도 표준 보고 산출물의 준비 상태를 현재 데이터로 점검하고, 운영실태 보고서 초안을 미리 봅니다.
        {loading && ' 데이터를 불러오는 중…'}
        {failed > 0 && ` (일부 데이터 ${failed}건을 불러오지 못했습니다 — 권한 또는 연결 확인)`}
      </p>

      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {cards.map((c) => (
          <Card key={c.id}>
            <CardHeader className="pb-2">
              <CardTitle className="flex items-start justify-between gap-2 text-base">
                <span>{c.title}</span>
                <Badge variant="outline" className={`shrink-0 ${READINESS_STYLE[c.readiness]}`}>
                  {READINESS_LABEL[c.readiness]}
                </Badge>
              </CardTitle>
              <p className="text-xs text-muted-foreground">{c.audience}</p>
            </CardHeader>
            <CardContent className="space-y-2 text-sm">
              <div>
                <span className="font-medium">구성: </span>{c.contents.join(' · ')}
              </div>
              <div>
                <span className="font-medium">데이터 출처: </span>{c.sources.join(', ')}
              </div>
              <div className="text-muted-foreground">{c.note}</div>
            </CardContent>
          </Card>
        ))}
      </div>

      <OpsReportPreview facts={facts} scopingStatusLabel={scopingStatusLabel} />
    </div>
  )
}

const PRINT_CSS = `
  body { font-family: 'Malgun Gothic', 'Apple SD Gothic Neo', sans-serif; margin: 24mm 18mm; color: #111; line-height: 1.6; }
  h2 { font-size: 20px; text-align: center; margin-bottom: 4px; }
  h3 { font-size: 15px; margin: 18px 0 6px; border-bottom: 1px solid #999; padding-bottom: 2px; }
  table { border-collapse: collapse; width: 100%; font-size: 13px; }
  th, td { border: 1px solid #999; padding: 4px 8px; text-align: left; }
  p, li { font-size: 13px; }
  .muted { color: #666; font-size: 12px; }
`

function OpsReportPreview({ facts: f, scopingStatusLabel }: { facts: ReportFacts; scopingStatusLabel: string | null }) {
  const ref = useRef<HTMLDivElement>(null)
  const fy = f.fiscalYear ? `${f.fiscalYear}` : '(미정)'

  // 레이아웃(사이드바·헤더)을 건드릴 수 없으므로 미리보기 영역만 새 창에 옮겨 인쇄한다.
  const print = () => {
    const w = window.open('', '_blank', 'width=900,height=1000')
    if (!w || !ref.current) return
    w.document.write(
      `<!doctype html><html lang="ko"><head><meta charset="utf-8"><title>${fy} 내부회계관리제도 운영실태 보고서(초안)</title><style>${PRINT_CSS}</style></head><body>${ref.current.innerHTML}</body></html>`,
    )
    w.document.close()
    w.focus()
    w.print()
  }

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="flex flex-wrap items-center justify-between gap-2 text-base">
          운영실태 보고서 초안 미리보기
          <Button size="sm" variant="outline" onClick={print}>
            <Printer className="mr-1 h-4 w-4" />인쇄
          </Button>
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div ref={ref} className="space-y-4 rounded-md border bg-white p-4 text-sm text-slate-900 [&_h3]:mt-4 [&_h3]:border-b [&_h3]:pb-1 [&_h3]:font-semibold [&_table]:w-full [&_td]:border [&_td]:px-2 [&_td]:py-1 [&_th]:border [&_th]:bg-slate-50 [&_th]:px-2 [&_th]:py-1 [&_th]:text-left">
          <h2 className="text-center text-lg font-bold">{fy} 회계연도 내부회계관리제도 운영실태 보고서</h2>
          <p className="muted text-center text-xs text-muted-foreground">
            대표이사 → 이사회 및 감사(위원회) · 초안(자동 집계, {new Date().toLocaleDateString('ko-KR')} 기준)
          </p>

          <h3>1. 평가 개요</h3>
          <table>
            <tbody>
              <tr><th>평가 기준연도</th><td>{fy} 회계연도 (기준일: {f.fiscalYear ? `${f.fiscalYear}-12-31` : '—'})</td></tr>
              <tr><th>평가 기준</th><td>내부회계관리제도 설계 및 운영 개념체계, 평가 및 보고 모범규준</td></tr>
              <tr><th>평가 범위</th><td>유의한 계정 {f.significantAccounts}개{f.unevaluatedAccounts > 0 ? ` (미평가 ${f.unevaluatedAccounts}개)` : ''} · 스코핑 상태 {scopingStatusLabel ?? '—'}</td></tr>
              <tr><th>평가 대상 통제</th><td>통제 {f.controlTotal}개 · 프로세스 {f.processTotal}개</td></tr>
            </tbody>
          </table>

          <h3>2. 운영효과성 테스트 결과</h3>
          <table>
            <thead><tr><th>테스트 회차</th><th>완료</th><th>미완료</th><th>효과적(pass)</th><th>비효과적(fail)</th><th>해당없음</th></tr></thead>
            <tbody>
              <tr><td>{f.tests.total}</td><td>{f.tests.done}</td><td>{f.tests.pending}</td><td>{f.tests.pass}</td><td>{f.tests.fail}</td><td>{f.tests.na}</td></tr>
            </tbody>
          </table>

          <h3>3. 통제 미비점</h3>
          <table>
            <thead><tr><th>심각도</th><th>건수</th></tr></thead>
            <tbody>
              <tr><td>상 (중요한 취약점 검토 대상)</td><td>{f.deficiencies.high}</td></tr>
              <tr><td>중 (유의한 미비점 검토 대상)</td><td>{f.deficiencies.medium}</td></tr>
              <tr><td>하 (단순 미비점)</td><td>{f.deficiencies.low}</td></tr>
              <tr><th>합계</th><th>{f.deficiencies.total} (미종결 {f.deficiencies.open} · 종결 {f.deficiencies.closed})</th></tr>
            </tbody>
          </table>
          <p className="muted text-xs text-muted-foreground">심각도 → 미비점 등급(중요한 취약점·유의한 미비점·단순 미비점) 대응은 초안 가정이며 최종 결론은 미비점별 평가를 따른다.</p>

          <h3>4. 개선계획 진행</h3>
          <table>
            <thead><tr><th>계획</th><th>진행중</th><th>완료</th><th>승인</th><th>합계</th></tr></thead>
            <tbody>
              <tr><td>{f.plans.planned}</td><td>{f.plans.inProgress}</td><td>{f.plans.completed}</td><td>{f.plans.approved}</td><td>{f.plans.total}</td></tr>
            </tbody>
          </table>

          <h3>5. 평가 결론</h3>
          <p>
            {f.tests.total === 0
              ? '운영효과성 테스트 결과가 아직 없어 결론을 작성할 수 없습니다.'
              : f.deficiencies.high > 0
                ? `중요한 취약점 검토 대상 미비점이 ${f.deficiencies.high}건 있어, 평가 결론 확정 전 미비점 평가가 필요합니다.`
                : `${fy} 회계연도 말 현재 당사의 내부회계관리제도는 내부회계관리제도 설계 및 운영 개념체계에 따라 중요성의 관점에서 효과적으로 설계·운영되고 있다고 판단됩니다. (초안 문구 — 미완료 테스트 ${f.tests.pending}건 반영 전)`}
          </p>
          <p className="muted text-xs text-muted-foreground">대표이사 ______________ (인) · 내부회계관리자 ______________ (인)</p>
        </div>
      </CardContent>
    </Card>
  )
}
