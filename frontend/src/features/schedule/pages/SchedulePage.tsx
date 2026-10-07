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
  buildColumns,
  currentFiscalYear,
  formatOffsetRange,
  periodToSpan,
  phasesAt,
  phasesStartingAt,
  todayOffset,
  itemsToPhases,
  offsetsToDates,
  planChanges,
  type SchedulePhase,
} from '../schedule.pure'
import { errDetail, usePlan, usePlanAction, useTemplates } from '../api/usePlan'
import PlanGantt, { type GanttBar } from '../components/PlanGantt'
import { toast } from 'sonner'
import { Pencil, Eye } from 'lucide-react'
import { endMonthOf, fiscalRangeText } from '@/lib/fiscalYear'
import PlanPanel from '../components/PlanPanel'

/**
 * 일정관리 — 회계연도 일정안(표준·사용자 지정, 전결라인 결재) + 평가 회차 기간 오버레이(2026-10-06).
 * 화면(간트·이번 달 할 일)은 **마지막 승인본**만 보여 준다. 승인본이 없으면 표준 일정(회사 표준 → 시스템 기본 8개).
 * [일정 편집]을 켜면 작성 중 판을 막대로 끌어 고친다 — 결재 승인 때 화면에 반영된다(13.9-100).
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
  const approvedItems = plan.data?.approved_items ?? null
  const phases: SchedulePhase[] = useMemo(() => {
    if (approvedItems) return itemsToPhases(approvedItems, fy, startMonth)
    if (tpl.data) {
      return tpl.data.items.map((t) => ({ id: t.code, name: t.name, category: (t.category === 'other' ? 'audit' : t.category) as SchedulePhase['category'],
        start: t.start_offset, end: t.end_offset, description: t.description ?? '', tasks: t.tasks }))
    }
    return STANDARD_TEMPLATE
  }, [approvedItems, tpl.data, fy, startMonth])

  // 간트 — 보기(승인본/표준) 또는 편집(작성 중 판, 끌어서 고침)
  const [editing, setEditing] = useState(false)
  const action = usePlanAction(fy)
  const p = plan.data?.plan ?? null
  const canEdit = !!plan.data?.can.edit
  const locked = p?.status === 'in_review'
  const viewBars: GanttBar[] = useMemo(() => {
    if (approvedItems) return approvedItems.map((it) => ({ id: it.id, label: it.title, start: it.start_date, end: it.end_date,
      barClass: CATEGORY_STYLE[(it.category in CATEGORY_STYLE ? it.category : 'audit') as SchedulePhase['category']], title: it.description ?? undefined }))
    return phases.map((ph) => ({ id: ph.id, label: ph.name, ...offsetsToDates(fy, startMonth, ph.start, ph.end),
      barClass: CATEGORY_STYLE[ph.category], title: ph.description }))
  }, [approvedItems, phases, fy, startMonth])
  const editBars: GanttBar[] = useMemo(() => {
    if (!plan.data?.plan) return []
    const ch = planChanges(plan.data.items, approvedItems)
    return plan.data.items.map((it) => ({ id: it.id, label: it.title, start: it.start_date, end: it.end_date,
      barClass: CATEGORY_STYLE[(it.category in CATEGORY_STYLE ? it.category : 'audit') as SchedulePhase['category']],
      title: it.description ?? undefined, editable: canEdit && !locked,
      mark: ch.added.has(it.id) ? 'added' as const : ch.changed.has(it.id) ? 'changed' as const : undefined }))
  }, [plan.data, approvedItems, canEdit, locked])
  const pendingChanges = useMemo(() => {
    if (!plan.data?.plan || !approvedItems) return null
    const ch = planChanges(plan.data.items, approvedItems)
    return ch.changed.size + ch.added.size + ch.removed.length
  }, [plan.data, approvedItems])
  const commit = (id: string, start: string, end: string) => {
    action.mutate({ method: 'patch', path: `/items/${id}/dates`, body: { start_date: start, end_date: end } }, {
      onSuccess: () => toast.success(`작성 중 판에 저장했습니다 (${start} ~ ${end}) — 결재 승인 후 화면에 반영됩니다`),
      onError: (e) => toast.error(errDetail(e, '기간을 바꾸지 못했습니다')),
    })
  }
  const cycleBars: GanttBar[] = fyCyclesBars(cycles, fy, startMonth)
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
          <div className="mt-2 flex flex-wrap gap-1.5">
            <Badge variant="outline">
              {p?.approved_version ? `승인본 ${p.approved_version}판 표시 중` : '승인된 일정안 없음 — 표준 일정 표시 중'}
            </Badge>
            {p && (p.status !== 'approved' || p.version !== p.approved_version) && (
              <Badge variant="outline" className="border-amber-300 bg-amber-50 text-amber-800 dark:bg-amber-950/30 dark:text-amber-300">
                작성 중 {p.version}판 · {p.status_label}{pendingChanges ? ` · 승인본 대비 변경 ${pendingChanges}건` : ''}
              </Badge>
            )}
          </div>
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
        <CardHeader className="flex flex-row flex-wrap items-center justify-between gap-2 space-y-0 pb-2">
          <div>
            <CardTitle className="text-base">연간 일정 {editing && <span className="text-sm font-normal text-amber-700 dark:text-amber-300">· 편집 중({p ? `${p.version}판` : '일정안 없음'})</span>}</CardTitle>
            <p className="mt-0.5 text-xs text-muted-foreground">
              {editing
                ? locked ? '결재 중에는 고칠 수 없습니다 — 반려되거나 승인된 뒤 고치세요.'
                  : '막대 가운데를 끌어 옮기고, 양 끝을 끌어 늘이거나 줄입니다. 놓으면 작성 중 판에 저장되고, 결재 승인 때 화면에 반영됩니다.'
                : p?.approved_version ? '승인된 일정입니다.' : '표준 일정입니다 — 일정안을 만들어 결재받으면 그 일정으로 바뀝니다.'}
            </p>
          </div>
          {canEdit && (
            <div className="hidden gap-1 md:flex">
              <Button size="sm" variant={editing ? 'ghost' : 'outline'} onClick={() => setEditing(false)} aria-pressed={!editing}>
                <Eye className="mr-1 h-3.5 w-3.5" />승인본 보기
              </Button>
              <Button size="sm" variant={editing ? 'default' : 'outline'} onClick={() => setEditing(true)} aria-pressed={editing}>
                <Pencil className="mr-1 h-3.5 w-3.5" />일정 편집
              </Button>
            </div>
          )}
        </CardHeader>
        <CardContent>
          {/* 데스크톱: 일 단위 간트(편집 모드면 끌어서 고침) */}
          <div className="hidden md:block">
            {editing && !p ? (
              <div className="flex flex-col items-center gap-2 rounded-lg border border-dashed p-6 text-sm text-muted-foreground">
                아직 {fy} 회계연도 일정안이 없습니다.
                <Button size="sm" disabled={action.isPending}
                  onClick={() => action.mutate({ method: 'post', path: '/init' }, { onError: (e) => toast.error(errDetail(e, '만들지 못했습니다')) })}>
                  표준 일정으로 일정안 만들기
                </Button>
              </div>
            ) : (
              <PlanGantt fy={fy} startMonth={startMonth} columns={columns} nowOffset={nowOffset}
                rows={editing ? editBars : viewBars} onCommit={editing ? commit : undefined}
                section={{ title: '평가 회차 (실제 기간)', rows: cycleBars }} />
            )}
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

/** 평가 회차(실제 기간) — 이 회계연도 그리드에 걸치는 것만 */
function fyCyclesBars(cycles: CycleItem[], fy: number, startMonth: number): GanttBar[] {
  return cycles
    .filter((c) => periodToSpan(fy, startMonth, c.period_start, c.period_end) !== null)
    .map((c) => ({ id: `cycle-${c.id}`, label: c.name, start: c.period_start, end: c.period_end,
      barClass: c.status === 'open' ? 'bg-primary/80' : 'bg-muted-foreground/50', title: `${c.period_start} ~ ${c.period_end}` }))
}
