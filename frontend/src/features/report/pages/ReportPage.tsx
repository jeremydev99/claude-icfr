import { useMemo, useRef, type ReactNode } from 'react'
import { Printer } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import HelpButton from '@/features/help/HelpButton'
import ReportPackage from '../components/ReportPackage'
import { useFiscal } from '@/lib/useFiscal'
import { fyLabel } from '@/lib/fiscalYear'
import { useScopingMeta, useScopingSummary } from '@/features/scoping/api/useScoping'
import { useRcmSummary } from '@/features/dashboard/api/useRcmSummary'
import { useTestRuns } from '@/features/test/api/useTestRuns'
import { useDeficiencies } from '@/features/remediation/api/useDeficiencies'
import { usePlans } from '@/features/remediation/api/useRemediationPlans'
import { useEvidenceFiles } from '@/features/evidence/api/useEvidence'
import { useFsStatements } from '@/features/financial-statements/api/useFs'
import {
  CONCLUSION_BASIS, CONCLUSION_DRAFT_NOTE, DASH, DEFICIENCY_CLASS_LABEL, DEFICIENCY_CLASS_ORDER,
  MISSING_HINT, READINESS_LABEL, buildReportCards, computeFacts, display, evaluationDate,
  selectAuditCommitteeConclusion, selectConclusion, type Conclusion, type ReportFacts, type Readiness,
} from '../reportModel'

// 초안: 전용 집계 API가 없어 목록 API를 넉넉한 limit 으로 받아 화면에서 센다.
const ALL = { limit: 1000 }

const READINESS_STYLE: Record<Readiness, string> = {
  ready: 'border-emerald-300 bg-emerald-50 text-emerald-900',
  partial: 'border-amber-300 bg-amber-50 text-amber-900',
  empty: 'border-slate-300 bg-slate-50 text-slate-600',
}

// 보고서 문서 스타일 — 화면 미리보기와 인쇄 창이 같은 CSS 를 쓴다(.icfr-report 하위로 한정).
const DOC_CSS = `
.icfr-report { background:#fff; color:#111; font-family:'Malgun Gothic','Apple SD Gothic Neo',sans-serif; line-height:1.6; font-size:13px; max-width:100%; overflow-wrap:anywhere; }
.icfr-report h2 { font-size:19px; font-weight:700; text-align:center; margin:0 0 2px; }
.icfr-report h3 { font-size:14.5px; font-weight:700; margin:20px 0 6px; padding-bottom:2px; border-bottom:1px solid #888; }
.icfr-report .sub { text-align:center; color:#555; font-size:12px; margin:0 0 4px; }
.icfr-report .draft { display:inline-block; border:1px solid #d97706; color:#b45309; border-radius:4px; padding:0 6px; font-size:11px; font-weight:600; }
.icfr-report .tbl { overflow-x:auto; }
.icfr-report table { border-collapse:collapse; width:100%; margin:4px 0; }
.icfr-report th, .icfr-report td { border:1px solid #999; padding:4px 8px; text-align:left; vertical-align:top; }
.icfr-report th { background:#f3f4f6; font-weight:600; white-space:nowrap; }
.icfr-report td.n, .icfr-report th.n { text-align:right; white-space:nowrap; }
.icfr-report p { margin:4px 0; }
.icfr-report ul { margin:4px 0; padding-left:20px; }
.icfr-report .muted { color:#666; font-size:11.5px; }
.icfr-report .hint { color:#888; font-size:11px; margin-left:4px; }
.icfr-report .conclusion { border:1px solid #999; padding:10px 12px; margin:6px 0; }
.icfr-report .memo { border:1px dashed #d97706; background:#fffbeb; padding:6px 10px; margin-top:6px; }
.icfr-report .sign { margin-top:28px; display:grid; grid-template-columns:repeat(auto-fit,minmax(200px,1fr)); gap:14px 24px; }
.icfr-report .sign div { white-space:nowrap; }
`

// 브라우저 인쇄(Ctrl+P)로 찍어도 앱 화면 대신 선택된 보고서만 나오게 — 이 페이지가 떠 있을 때만 적용된다.
const PAGE_PRINT_CSS = `
@media print {
  @page { size: A4; margin: 18mm 16mm; }
  body * { visibility: hidden !important; }
  .icfr-print-area, .icfr-print-area * { visibility: visible !important; }
  .icfr-print-area { position: absolute; left: 0; top: 0; width: 100%; border: 0 !important; padding: 0 !important; }
  .icfr-report table, .icfr-report .conclusion, .icfr-report .sign { break-inside: avoid; }
  .icfr-report h3 { break-after: avoid; }
  .icfr-report .memo { display: none; }
}
`

// 새 창 인쇄용 — 앱 레이아웃 없이 문서만. 확정 전 메모(.memo)는 인쇄하지 않는다.
const WINDOW_PRINT_CSS = `
@page { size: A4; margin: 18mm 16mm; }
body { margin: 0; }
.icfr-report table, .icfr-report .conclusion, .icfr-report .sign { break-inside: avoid; }
.icfr-report h3 { break-after: avoid; }
.icfr-report .memo { display: none; }
`

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
    <div className="mx-auto min-w-0 max-w-[1400px] space-y-6 p-6 md:p-8">
      <style>{DOC_CSS + PAGE_PRINT_CSS}</style>
      <div className="flex flex-wrap items-center gap-2">
        <h1 className="text-2xl font-bold tracking-tight">Report</h1>
        <Badge variant="outline" className="border-amber-300 bg-amber-50 text-amber-900">
          문단을 눌러 고칠 수 있습니다 — 고친 부분만 저장
        </Badge>
      </div>
      <p className="text-sm text-muted-foreground">
        외부감사법 제8조에 따른 법정 보고서 2종, 이사회 보고 자료, 감사위원회·이사회 의사록(안)을 한 패키지로 만듭니다. 별첨 탭에는 평가 결과 데이터(실무 양식)가 있습니다.
        모든 수치는 각 메뉴의 실제 데이터이며, 데이터가 없으면 "{DASH}"로 표시합니다.
        {loading && ' 데이터를 불러오는 중…'}
        {failed > 0 && ` (일부 데이터 ${failed}건을 불러오지 못했습니다 — 권한 또는 연결 확인)`}
      </p>

      <Tabs defaultValue="package" className="space-y-4">
        <TabsList className="flex h-auto w-full flex-wrap justify-start sm:w-auto">
          <TabsTrigger value="package">이사회 보고 패키지</TabsTrigger>
          <TabsTrigger value="appendix">별첨 · 평가 결과 데이터</TabsTrigger>
        </TabsList>
        <span className="ml-1 inline-flex gap-1 align-middle">
          <HelpButton k="screen.report.package" />
          <HelpButton k="screen.report.appendix" />
        </span>
        <TabsContent value="package"><ReportPackage facts={facts} /></TabsContent>
        <TabsContent value="appendix" className="space-y-6">
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {cards.map((c) => (
              <Card key={c.id} className="min-w-0">
                <CardHeader className="pb-2">
                  <CardTitle className="flex items-start justify-between gap-2 text-base">
                    <span>{c.title}</span>
                    <Badge variant="outline" className={`shrink-0 ${READINESS_STYLE[c.readiness]}`}>
                      {READINESS_LABEL[c.readiness]}
                    </Badge>
                  </CardTitle>
                  <p className="text-xs text-muted-foreground">
                    {c.statutory ? '법정 보고서 · ' : '보조 산출물 · '}{c.audience}
                  </p>
                </CardHeader>
                <CardContent className="space-y-2 text-sm">
                  <div><span className="font-medium">구성: </span>{c.contents.join(' · ')}</div>
                  <div><span className="font-medium">데이터 출처: </span>{c.sources.join(', ')}</div>
                  <div className="text-muted-foreground">{c.note}</div>
                </CardContent>
              </Card>
            ))}
          </div>

          <Tabs defaultValue="ops" className="space-y-3">
            <TabsList className="flex h-auto w-full flex-wrap justify-start sm:w-auto">
              <TabsTrigger value="ops">운영실태 보고서</TabsTrigger>
              <TabsTrigger value="audit">감사(위원회) 평가보고서</TabsTrigger>
            </TabsList>
            <span className="ml-1 inline-flex gap-1 align-middle">
              <HelpButton k="screen.report.operation-report" />
              <HelpButton k="screen.report.audit-committee-report" />
            </span>
            <TabsContent value="ops">
              <PreviewCard heading="내부회계관리제도 운영실태 보고서 — 초안 미리보기" docTitle={`${facts.fiscalYear ?? ''} 내부회계관리제도 운영실태 보고서(초안)`}>
                <OpsReport f={facts} scopingStatusLabel={scopingStatusLabel} />
              </PreviewCard>
            </TabsContent>
            <TabsContent value="audit">
              <PreviewCard heading="감사(위원회)의 내부회계관리제도 평가보고서 — 초안 미리보기" docTitle={`${facts.fiscalYear ?? ''} 감사(위원회)의 내부회계관리제도 평가보고서(초안)`}>
                <AuditCommitteeReport f={facts} />
              </PreviewCard>
            </TabsContent>
          </Tabs>
        </TabsContent>
      </Tabs>
    </div>
  )
}

function PreviewCard({ heading, docTitle, children }: { heading: string; docTitle: string; children: ReactNode }) {
  const ref = useRef<HTMLDivElement>(null)

  // 미리보기 영역만 새 창에 옮겨 인쇄한다(앱 레이아웃 제외). 팝업이 막히면 브라우저 인쇄로 대신한다 —
  // 그때도 PAGE_PRINT_CSS 가 선택된 보고서만 남긴다.
  const print = () => {
    const w = window.open('', '_blank', 'width=900,height=1000')
    if (!w || !ref.current) { window.print(); return }
    const title = docTitle.trim().replace(/[<>&]/g, '')
    w.document.write(
      `<!doctype html><html lang="ko"><head><meta charset="utf-8"><title>${title}</title><style>${DOC_CSS}${WINDOW_PRINT_CSS}</style></head><body>${ref.current.innerHTML}</body></html>`,
    )
    w.document.close()
    w.focus()
    w.print()
  }

  return (
    <Card className="min-w-0">
      <CardHeader className="pb-2">
        <CardTitle className="flex flex-wrap items-center justify-between gap-2 text-base">
          {heading}
          <Button size="sm" variant="outline" onClick={print}>
            <Printer className="mr-1 h-4 w-4" />인쇄 (A4)
          </Button>
        </CardTitle>
        <p className="text-xs text-muted-foreground">
          점선 상자(확정 전 확인 사항)는 작성자용 메모이며 인쇄되지 않습니다.
        </p>
      </CardHeader>
      <CardContent className="min-w-0">
        <div className="icfr-print-area min-w-0 rounded-md border p-3 sm:p-6">
          <div ref={ref} className="icfr-report">{children}</div>
        </div>
      </CardContent>
    </Card>
  )
}

/** 숫자 칸 — 원천 데이터가 없으면 '—' 와 채울 메뉴 힌트. */
function Num({ v, ok = true, hint }: { v: number | null | undefined; ok?: boolean; hint?: string }) {
  const s = display(v, ok)
  return <>{s}{s === DASH && hint && <span className="hint">({hint})</span>}</>
}

function Draft() {
  return <span className="draft">초안</span>
}

function koDate(iso: string | null): string {
  if (!iso) return DASH
  return `${iso.slice(0, 4)}년 ${Number(iso.slice(5, 7))}월 ${Number(iso.slice(8, 10))}일`
}

function ConclusionBlock({ c }: { c: Conclusion }) {
  return (
    <>
      <div className="conclusion">
        <p>{c.text}</p>
        <p className="muted">※ {CONCLUSION_DRAFT_NOTE} · {CONCLUSION_BASIS}</p>
      </div>
      {c.caveats.length > 0 && (
        <div className="memo">
          <p className="muted"><b>확정 전 확인 사항</b> (보고서 본문 아님)</p>
          <ul>{c.caveats.map((t) => <li key={t} className="muted">{t}</li>)}</ul>
        </div>
      )}
    </>
  )
}

function SignBlock({ signers }: { signers: string[] }) {
  return (
    <>
      <p style={{ marginTop: 24, textAlign: 'center' }}>작성일: ______년 ____월 ____일</p>
      <div className="sign">
        {signers.map((s) => <div key={s}>{s} ______________ (인)</div>)}
      </div>
    </>
  )
}

function OpsReport({ f, scopingStatusLabel }: { f: ReportFacts; scopingStatusLabel: string | null }) {
  const fy = f.fiscalYear
  const { startMonth } = useFiscal()
  const date = evaluationDate(fy, startMonth)
  const conclusion = selectConclusion(f)
  const classTotal = f.deficiencies.total

  return (
    <>
      <h2>{fy ?? DASH} 회계연도 내부회계관리제도 운영실태 보고서</h2>
      <p className="sub">대표이사 → 이사회 및 감사(위원회) · <Draft /> 자동 집계 {new Date().toLocaleDateString('ko-KR')} 기준</p>

      <h3>Ⅰ. 개요</h3>
      <div className="tbl"><table><tbody>
        <tr><th>보고 목적</th><td>「주식회사 등의 외부감사에 관한 법률」 제8조에 따라 대표이사가 당해 회계연도 내부회계관리제도의 운영실태를 평가하여 이사회 및 감사(위원회)에 보고함</td></tr>
        <tr><th>평가 대상 회계연도</th><td>{fy ? fyLabel(fy, startMonth) : <Num v={null} hint={MISSING_HINT.fiscalYear} />}</td></tr>
        <tr><th>평가 기준일</th><td>{date ? `${koDate(date)} (회계연도 말)` : <Num v={null} hint={MISSING_HINT.fiscalYear} />}</td></tr>
        <tr><th>평가 기준</th><td>내부회계관리제도 설계 및 운영 개념체계, 내부회계관리제도 평가 및 보고 기준(모범규준)</td></tr>
        <tr><th>평가 수행</th><td>내부회계관리자 주관, 설계 평가(업무 흐름 검토) 및 운영 평가(표본 테스트)</td></tr>
      </tbody></table></div>

      <h3>Ⅱ. 평가 범위</h3>
      <div className="tbl"><table><tbody>
        <tr><th>유의한 계정·공시</th><td className="n"><Num v={f.significantAccounts} ok={f.has.scoping} hint={MISSING_HINT.scoping} /></td>
          <td>{f.has.scoping
            ? <>{f.significantByStatement.map((s) => `${s.statement} ${s.significant}`).join(' · ')}{f.unevaluatedAccounts > 0 && ` (미평가 ${f.unevaluatedAccounts}개)`} · 스코핑 상태 {scopingStatusLabel ?? DASH}</>
            : DASH}</td></tr>
        <tr><th>평가 대상 프로세스</th><td className="n"><Num v={f.processTotal} ok={f.has.rcm} hint={MISSING_HINT.rcm} /></td><td>RCM 기준</td></tr>
        <tr><th>평가 대상 통제</th><td className="n"><Num v={f.controlTotal} ok={f.has.rcm} hint={MISSING_HINT.rcm} /></td>
          <td>핵심통제 <Num v={f.keyControls} ok={f.has.rcm} /></td></tr>
        <tr><th>전사적 통제 / IT일반통제</th><td className="n">{DASH}</td><td><span className="hint">{MISSING_HINT.controlType}</span></td></tr>
      </tbody></table></div>
      {f.processes.length > 0 && (
        <div className="tbl"><table>
          <thead><tr><th>프로세스</th><th className="n">통제 수</th></tr></thead>
          <tbody>{f.processes.map((p) => <tr key={p.label}><td>{p.label}</td><td className="n">{p.count}</td></tr>)}</tbody>
        </table></div>
      )}

      <h3>Ⅲ. 설계 및 운영 평가 결과</h3>
      <div className="tbl"><table>
        <thead><tr><th>평가 대상</th><th className="n">설계평가 기록</th><th className="n">운영평가 완료</th><th className="n">효과적</th><th className="n">비효과적</th><th className="n">해당없음</th><th className="n">미완료</th></tr></thead>
        <tbody><tr>
          {[f.tests.total, f.designRecorded, f.tests.done, f.tests.pass, f.tests.fail, f.tests.na, f.tests.pending].map((v, idx) => (
            <td key={idx} className="n"><Num v={v} ok={f.has.tests} /></td>
          ))}
        </tr></tbody>
      </table></div>
      {!f.has.tests && <p className="muted">{MISSING_HINT.tests}</p>}
      <p className="muted">설계평가 기록 = 업무 흐름 검토(WTT) 요약이 작성된 테스트 수. 효과적·비효과적은 운영평가 결과 기준.</p>

      <h3>Ⅳ. 미비점 현황</h3>
      <div className="tbl"><table>
        <thead><tr><th>구분</th><th className="n">발견</th><th className="n">미종결</th></tr></thead>
        <tbody>
          {DEFICIENCY_CLASS_ORDER.map((k) => (
            <tr key={k}><td>{DEFICIENCY_CLASS_LABEL[k]}</td>
              <td className="n"><Num v={f.byClass[k].total} ok={f.has.deficiencies} /></td>
              <td className="n"><Num v={f.byClass[k].open} ok={f.has.deficiencies} /></td></tr>
          ))}
          <tr><th>합계</th><th className="n"><Num v={classTotal} ok={f.has.deficiencies} /></th><th className="n"><Num v={f.deficiencies.open} ok={f.has.deficiencies} /></th></tr>
        </tbody>
      </table></div>
      {!f.has.deficiencies && <p className="muted">{MISSING_HINT.deficiencies}</p>}
      <p className="muted">등급은 시스템 심각도(높음→중요한 취약점, 중간→유의한 미비점, 낮음→단순한 미비점)에서 대응시킨 초안이며, 최종 등급은 미비점별 평가로 확정한다.</p>

      <p style={{ marginTop: 10 }}><b>개선계획 진행</b></p>
      <div className="tbl"><table>
        <thead><tr><th className="n">계획</th><th className="n">진행중</th><th className="n">완료</th><th className="n">승인</th><th className="n">합계</th><th className="n">계획 없는 미비점</th></tr></thead>
        <tbody><tr>
          {[f.plans.planned, f.plans.inProgress, f.plans.completed, f.plans.approved, f.plans.total, f.deficienciesWithoutPlan].map((v, idx) => (
            <td key={idx} className="n"><Num v={v} ok={f.has.plans} /></td>
          ))}
        </tr></tbody>
      </table></div>
      {!f.has.plans && <p className="muted">{MISSING_HINT.plans}</p>}

      <h3>Ⅴ. 결론</h3>
      <ConclusionBlock c={conclusion} />

      <SignBlock signers={['대표이사', '내부회계관리자']} />
    </>
  )
}

function AuditCommitteeReport({ f }: { f: ReportFacts }) {
  const fy = f.fiscalYear
  const { startMonth } = useFiscal()
  const conclusion = selectAuditCommitteeConclusion(f)
  return (
    <>
      <h2>{fy ?? DASH} 회계연도 감사(위원회)의 내부회계관리제도 평가보고서</h2>
      <p className="sub">감사(위원회) → 이사회 · <Draft /> 자동 집계 {new Date().toLocaleDateString('ko-KR')} 기준</p>

      <h3>1. 평가 대상 기간</h3>
      <p>{fy ? fyLabel(fy, startMonth) : <Num v={null} hint={MISSING_HINT.fiscalYear} />}</p>

      <h3>2. 평가 방법 요약</h3>
      <ul>
        <li>대표이사가 보고한 내부회계관리제도 운영실태 보고서를 검토하였습니다.</li>
        <li>평가 범위의 적정성 — 유의한 계정·공시 <Num v={f.significantAccounts} ok={f.has.scoping} hint={MISSING_HINT.scoping} />개,
          평가 대상 통제 <Num v={f.controlTotal} ok={f.has.rcm} hint={MISSING_HINT.rcm} />개를 검토하였습니다.</li>
        <li>설계 및 운영 평가 결과 — 평가 대상 <Num v={f.tests.total} ok={f.has.tests} hint={MISSING_HINT.tests} />건 중
          완료 <Num v={f.tests.done} ok={f.has.tests} />건(비효과적 <Num v={f.tests.fail} ok={f.has.tests} />건)을 검토하였습니다.</li>
        <li>미비점 및 시정조치 — 미비점 <Num v={f.deficiencies.total} ok={f.has.deficiencies} hint={MISSING_HINT.deficiencies} />건
          (중요한 취약점 <Num v={f.byClass.material_weakness.total} ok={f.has.deficiencies} />건)과
          개선계획 <Num v={f.plans.total} ok={f.has.plans} />건의 적정성을 검토하였습니다.</li>
      </ul>

      <h3>3. 평가 결론</h3>
      <ConclusionBlock c={conclusion} />

      <SignBlock signers={['감사위원회 위원장(또는 감사)', '감사위원', '감사위원']} />
    </>
  )
}
