import EmptyState from '@/components/illustration/EmptyState'
import { useMemo, useState } from 'react'
import { CalendarDays, ChevronLeft, ChevronRight, Loader2 } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { useCycles, useFiscalStartMonth, useIncompleteCounts, type CycleItem } from '../api/useSchedule'
import { useAuthStore } from '@/features/auth/store'
import CycleCreateDialog from '@/features/assessment/components/CycleCreateDialog'
import {
  CATEGORY_STYLE,
  FREQ_LABEL,
  KIND_LABEL,
  STANDARD_TEMPLATE,
  STATUS_LABEL,
  TOTAL_COLUMNS,
  buildColumns,
  currentFiscalYear,
  formatOffsetRange,
  periodToSpan,
  phasesAt,
  phasesStartingAt,
  todayOffset,
  itemsToPhases,
  type MonthColumn,
  type SchedulePhase,
} from '../schedule.pure'
import { usePlan, useTemplates } from '../api/usePlan'
import { endMonthOf, fiscalRangeText } from '@/lib/fiscalYear'
import PlanPanel from '../components/PlanPanel'

/**
 * 일정관리 — 회계연도 일정안(표준·사용자 지정, 전결라인 결재) + 평가 회차 기간 오버레이(2026-10-06).
 * 일정안이 없으면 표준 일정(회사 표준 → 없으면 시스템 기본 8개)을 보여 준다.
 */
export default function SchedulePage() {
  const today = useMemo(() => new Date(), [])
  const { data: startMonth = 1, isLoading: loadingPolicy } = useFiscalStartMonth()
  const { data: cycles = [], isLoading: loadingCycles } = useCycles()
  const [fyOverride, setFy] = useState<number | null>(null)
  const thisFy = currentFiscalYear(today, startMonth)
  const fy = fyOverride ?? thisFy
  // 버튼은 외부감사인(조회 전용)만 숨긴다. 평가자 여부는 /me 에 없어 서버 403 사유로 안내한다
  const canWrite = useAuthStore((s) => s.user?.can_write ?? false)
  const [createOpen, setCreateOpen] = useState(false)

  const columns = useMemo(() => buildColumns(fy, startMonth), [fy, startMonth])
  const nowOffset = todayOffset(fy, startMonth, today)
  // 일정안이 있으면 그 항목(날짜)으로, 없으면 표준 일정(회사 표준 또는 시스템 기본)으로 그린다
  const plan = usePlan(fy)
  const tpl = useTemplates()
  const phases: SchedulePhase[] = useMemo(() => {
    if (plan.data?.plan) return itemsToPhases(plan.data.items, fy, startMonth)
    if (tpl.data) {
      return tpl.data.items.map((t) => ({ id: t.code, name: t.name, category: (t.category === 'other' ? 'audit' : t.category) as SchedulePhase['category'],
        start: t.start_offset, end: t.end_offset, description: t.description ?? '', tasks: t.tasks }))
    }
    return STANDARD_TEMPLATE
  }, [plan.data, tpl.data, fy, startMonth])
  const nowPhases = phasesAt(nowOffset, phases)
  const nextPhases = phasesStartingAt(nowOffset == null ? null : nowOffset + 1, phases)

  const fyCycles = useMemo(
    () =>
      cycles
        .map((c) => ({ c, span: periodToSpan(fy, startMonth, c.period_start, c.period_end) }))
        .filter((x): x is { c: CycleItem; span: { start: number; end: number } } => x.span !== null),
    [cycles, fy, startMonth],
  )
  const incomplete = useIncompleteCounts(fyCycles.map((x) => x.c))

  if (loadingPolicy) {
    return <div className="flex items-center gap-2 p-6 text-sm text-muted-foreground"><Loader2 className="h-4 w-4 animate-spin" /> 불러오는 중…</div>
  }

  return (
    <div className="mx-auto max-w-[1400px] space-y-6 p-6 md:p-8">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">일정관리</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            연간 ICFR 평가 일정 — {endMonthOf(startMonth)}월 결산({fiscalRangeText(fy, startMonth)}). 결산 후 3개월(결산·보고)까지 표시합니다.
          </p>
          <Badge variant="outline" className="mt-2">
            {plan.data?.plan ? `${fy} 일정안 · ${plan.data.plan.status_label}` : '일정안 없음 — 표준 일정 표시 중'}
          </Badge>
        </div>
        <div className="flex items-center gap-1">
          <Button variant="outline" size="icon" aria-label="이전 회계연도" onClick={() => setFy(fy - 1)}>
            <ChevronLeft className="h-4 w-4" />
          </Button>
          <span className="min-w-24 text-center text-sm font-medium leading-tight">{fy} 회계연도<br />
            <span className="text-xs font-normal text-muted-foreground">{fiscalRangeText(fy, startMonth)}</span></span>
          <Button variant="outline" size="icon" aria-label="다음 회계연도" onClick={() => setFy(fy + 1)}>
            <ChevronRight className="h-4 w-4" />
          </Button>
          {fyOverride !== null && (
            <Button variant="ghost" size="sm" onClick={() => setFy(null)}>올해</Button>
          )}
        </div>
      </div>

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="flex items-center gap-2 text-base">
            <CalendarDays className="h-4 w-4" /> 이번 달 할 일
          </CardTitle>
        </CardHeader>
        <CardContent className="text-sm">
          {nowOffset == null ? (
            <p className="text-muted-foreground">선택한 회계연도에는 이번 달이 포함되지 않습니다.</p>
          ) : (
            <div className="space-y-3">
              <p className="text-muted-foreground">
                {columns[nowOffset - 1].year}년 {columns[nowOffset - 1].month}월 · 진행 단계 {nowPhases.length}개
              </p>
              {nowPhases.length === 0 && <p className="text-muted-foreground">이번 달 진행 중인 일정이 없습니다.</p>}
              <ul className="grid gap-3 sm:grid-cols-2">
                {nowPhases.map((p) => (
                  <li key={p.id} className="rounded-md border p-3">
                    <div className="flex items-center gap-2 font-medium">
                      <span className={`inline-block h-2.5 w-2.5 rounded-full ${CATEGORY_STYLE[p.category]}`} />
                      {p.name}
                    </div>
                    <ul className="mt-1 list-disc pl-5 text-muted-foreground">
                      {p.tasks.map((t) => <li key={t}>{t}</li>)}
                    </ul>
                  </li>
                ))}
              </ul>
              {nextPhases.length > 0 && (
                <p className="text-muted-foreground">
                  다음 달 시작 예정: {nextPhases.map((p) => p.name).join(', ')}
                </p>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base">연간 일정</CardTitle>
        </CardHeader>
        <CardContent>
          {/* 데스크톱: 월 그리드 */}
          <div className="hidden md:block">
            <GanttGrid columns={columns} nowOffset={nowOffset}>
              {phases.map((p) => (
                <GanttRow key={p.id} label={p.name} title={p.description} start={p.start} end={p.end}
                  barClass={CATEGORY_STYLE[p.category]} nowOffset={nowOffset} />
              ))}
              {fyCycles.length > 0 && (
                <div className="col-span-full mt-2 border-t pt-2 text-xs font-medium text-muted-foreground">평가 회차 (실제 기간)</div>
              )}
              {fyCycles.map(({ c, span }) => (
                <GanttRow key={c.id} label={c.name} title={`${c.period_start} ~ ${c.period_end}`} start={span.start} end={span.end}
                  barClass={c.status === 'open' ? 'bg-primary/80' : 'bg-muted-foreground/50'} nowOffset={nowOffset} />
              ))}
            </GanttGrid>
          </div>
          {/* 모바일: 단계별 목록 */}
          <ul className="space-y-2 md:hidden">
            {phases.map((p) => {
              const active = nowOffset != null && p.start <= nowOffset && nowOffset <= p.end
              return (
                <li key={p.id} className={`rounded-md border p-3 text-sm ${active ? 'border-primary bg-primary/5' : ''}`}>
                  <div className="flex items-center gap-2 font-medium">
                    <span className={`inline-block h-2.5 w-2.5 shrink-0 rounded-full ${CATEGORY_STYLE[p.category]}`} />
                    {p.name}
                    {active && <Badge className="ml-auto">진행 중</Badge>}
                  </div>
                  <div className="mt-1 text-xs text-muted-foreground">{formatOffsetRange(fy, startMonth, p.start, p.end)}</div>
                  <div className="mt-1 text-xs text-muted-foreground">{p.description}</div>
                </li>
              )
            })}
          </ul>
        </CardContent>
      </Card>

      {plan.data && <PlanPanel fy={fy} data={plan.data} />}

      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-base">평가 회차</CardTitle>
          {canWrite && <Button size="sm" onClick={() => setCreateOpen(true)}>회차 생성</Button>}
        </CardHeader>
        <CardContent className="text-sm">
          {loadingCycles ? (
            <div className="flex items-center gap-2 text-muted-foreground"><Loader2 className="h-4 w-4 animate-spin" /> 불러오는 중…</div>
          ) : fyCycles.length === 0 ? (
            <EmptyState
              compact
              slot="empty-checklist"
              title={`${fy} 회계연도에 해당하는 평가 회차가 없습니다`}
              description="평가자가 [회차 생성]으로 만들면 여기에 기간이 표시됩니다."
            />
          ) : (
            <ul className="divide-y">
              {fyCycles.map(({ c }) => (
                <li key={c.id} className="flex flex-wrap items-center gap-x-3 gap-y-1 py-2">
                  <span className="font-medium">{c.name}</span>
                  <Badge variant="secondary">{KIND_LABEL[c.kind] ?? c.kind}</Badge>
                  <Badge variant="outline">{FREQ_LABEL[c.frequency] ?? c.frequency}</Badge>
                  <Badge variant={c.status === 'open' ? 'default' : 'outline'}>{STATUS_LABEL[c.status] ?? c.status}</Badge>
                  <span className="text-muted-foreground">
                    {c.period_start} ~ {c.period_end}
                    {c.due_date && ` · 기한 ${c.due_date}`}
                  </span>
                  <span className="text-muted-foreground sm:ml-auto">
                    대상 {c.target_count ?? '-'}건
                    {incomplete[c.id] !== undefined && (
                      <span className={incomplete[c.id]! > 0 ? 'text-destructive' : ''}> · 미완 {incomplete[c.id]}건</span>
                    )}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>

      <CycleCreateDialog open={createOpen} onOpenChange={setCreateOpen} fiscalYear={fy} currentFiscalYear={thisFy} />
    </div>
  )
}

const GRID_STYLE = { gridTemplateColumns: `minmax(10rem, 14rem) repeat(${TOTAL_COLUMNS}, minmax(0, 1fr))` }

function GanttGrid({ columns, nowOffset, children }: { columns: MonthColumn[]; nowOffset: number | null; children: React.ReactNode }) {
  return (
    <div className="grid gap-y-1 text-xs" style={GRID_STYLE}>
      <div />
      {columns.map((col) => (
        <div
          key={col.offset}
          className={`py-1 text-center ${col.nextYear ? 'bg-muted/60' : ''} ${col.offset === nowOffset ? 'rounded-t bg-primary/15 font-semibold text-primary' : 'text-muted-foreground'}`}
          title={`${col.year}년 ${col.month}월${col.nextYear ? ' (익년)' : ''}`}
        >
          {col.month === 1 || col.offset === 1 ? <div className="text-[10px]">{col.year}</div> : <div className="text-[10px]">&nbsp;</div>}
          {col.label}
        </div>
      ))}
      {children}
    </div>
  )
}

function GanttRow({ label, title, start, end, barClass, nowOffset }: {
  label: string; title: string; start: number; end: number; barClass: string; nowOffset: number | null
}) {
  return (
    <>
      <div className="truncate pr-2 leading-6" title={label}>{label}</div>
      <div className="relative grid" style={{ gridColumn: `2 / span ${TOTAL_COLUMNS}`, gridTemplateColumns: `repeat(${TOTAL_COLUMNS}, minmax(0, 1fr))` }}>
        {nowOffset != null && (
          <div className="pointer-events-none bg-primary/10" style={{ gridColumn: `${nowOffset} / span 1`, gridRow: 1 }} />
        )}
        <div
          className={`my-1 h-4 rounded ${barClass}`}
          style={{ gridColumn: `${start} / ${end + 1}`, gridRow: 1 }}
          title={title}
        />
      </div>
    </>
  )
}
