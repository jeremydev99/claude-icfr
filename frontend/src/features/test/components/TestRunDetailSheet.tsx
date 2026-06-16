import { CheckCircle2, Circle, Loader2 } from 'lucide-react'
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet'
import { Separator } from '@/components/ui/separator'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { toast } from 'sonner'
import { useTestRunDetail, useTestRunHistory, useTransitionTestRun } from '../api/useTestRuns'
import {
  STATUS_LABELS,
  STATUS_BADGE_CLASS,
  RESULT_LABELS,
  RESULT_BADGE_CLASS,
  type TestRun,
  type TestRunStatus,
} from '../types'
import type { Control } from '@/features/rcm/types'

interface Props {
  runId: string | null
  open: boolean
  onOpenChange: (open: boolean) => void
  controlMap?: Record<string, Control>
}

type RunKey = keyof TestRun

const TEST_METHODS: { key: RunKey; label: string }[] = [
  { key: 'method_inspection', label: '검사' },
  { key: 'method_reperformance', label: '재수행' },
  { key: 'method_observation', label: '관찰' },
  { key: 'method_inquiry', label: '질문' },
]

const NEXT_TRANSITION: Record<TestRunStatus, { label: string; to_status: 'in_progress' | 'completed' | 'approved' } | null> = {
  planned: { label: '테스트 시작', to_status: 'in_progress' },
  in_progress: { label: '테스트 완료', to_status: 'completed' },
  completed: { label: '승인', to_status: 'approved' },
  approved: null,
}

function InfoRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="grid grid-cols-[120px_1fr] gap-2 py-1.5 text-sm">
      <span className="text-muted-foreground shrink-0">{label}</span>
      <span className="break-words">{value ?? '—'}</span>
    </div>
  )
}

function SectionTitle({ children }: { children: React.ReactNode }) {
  return <p className="text-sm font-semibold text-foreground mt-6 mb-1">{children}</p>
}

export default function TestRunDetailSheet({ runId, open, onOpenChange, controlMap }: Props) {
  const { data: run, isLoading } = useTestRunDetail(runId)
  const { data: historyData } = useTestRunHistory(runId)
  const transition = useTransitionTestRun()

  const ctrl = run ? controlMap?.[run.control_id] : undefined
  const nextTrans = run ? NEXT_TRANSITION[run.status] : null

  const handleTransition = () => {
    if (!run || !nextTrans) return
    transition.mutate(
      { id: run.id, payload: { to_status: nextTrans.to_status } },
      {
        onSuccess: () => toast.success(`상태가 '${STATUS_LABELS[nextTrans.to_status]}'로 변경되었습니다`),
        onError: () => toast.error('상태 변경에 실패했습니다'),
      },
    )
  }

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="sm:max-w-xl overflow-y-auto">
        {isLoading ? (
          <div className="flex items-center justify-center h-40">
            <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
          </div>
        ) : run ? (
          <>
            <SheetHeader className="pr-2">
              <div className="flex items-center gap-2 flex-wrap">
                <SheetTitle className="text-xl font-bold">
                  {ctrl?.code ?? run.control_id.slice(0, 8) + '...'}
                </SheetTitle>
                <Badge variant="outline" className={STATUS_BADGE_CLASS[run.status]}>
                  {STATUS_LABELS[run.status]}
                </Badge>
              </div>
              {ctrl && <p className="text-sm text-muted-foreground">{ctrl.name}</p>}
            </SheetHeader>

            <div className="mt-4 space-y-1">
              <SectionTitle>기본 정보</SectionTitle>
              <Separator />
              <InfoRow label="회계연도" value={run.fiscal_year} />
              <InfoRow label="평가일" value={run.test_date?.slice(0, 10)} />
              <InfoRow label="샘플 수" value={run.sample_size} />
              <InfoRow
                label="결과"
                value={
                  run.result ? (
                    <Badge variant="outline" className={RESULT_BADGE_CLASS[run.result]}>
                      {RESULT_LABELS[run.result]}
                    </Badge>
                  ) : undefined
                }
              />
              <InfoRow
                label="평가 방법"
                value={
                  <div className="flex flex-wrap gap-x-4 gap-y-1 mt-0.5">
                    {TEST_METHODS.map(({ key, label }) => {
                      const active = run[key] as boolean
                      return (
                        <span key={key} className="flex items-center gap-1 text-sm">
                          {active
                            ? <CheckCircle2 className="h-3.5 w-3.5 text-green-500" />
                            : <Circle className="h-3.5 w-3.5 text-muted-foreground/40" />
                          }
                          <span className={active ? '' : 'text-muted-foreground'}>{label}</span>
                        </span>
                      )
                    })}
                  </div>
                }
              />

              <SectionTitle>워크플로</SectionTitle>
              <Separator />
              <div className="py-2">
                {nextTrans ? (
                  <Button
                    size="sm"
                    onClick={handleTransition}
                    disabled={transition.isPending}
                  >
                    {transition.isPending && (
                      <Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" />
                    )}
                    {nextTrans.label}
                  </Button>
                ) : (
                  <span className="text-sm text-muted-foreground">최종 승인 완료</span>
                )}
              </div>

              <SectionTitle>상태 이력</SectionTitle>
              <Separator />
              <div className="py-2">
                {(historyData?.items ?? []).length === 0 ? (
                  <p className="text-sm text-muted-foreground">이력 없음</p>
                ) : (
                  <ol className="relative border-l border-muted-foreground/20 ml-2 space-y-4">
                    {[...(historyData?.items ?? [])].reverse().map((h) => (
                      <li key={h.id} className="ml-4">
                        <span className="absolute -left-1.5 mt-1 h-3 w-3 rounded-full border-2 border-background bg-muted-foreground/40" />
                        <div className="text-sm font-medium">
                          {h.from_status
                            ? `${STATUS_LABELS[h.from_status as TestRunStatus]} → `
                            : ''}
                          {STATUS_LABELS[h.to_status as TestRunStatus]}
                        </div>
                        <div className="text-xs text-muted-foreground mt-0.5">
                          {h.changed_by.display_name} · {h.changed_at.slice(0, 10)}
                        </div>
                        {h.reason && (
                          <div className="text-xs text-muted-foreground mt-0.5">{h.reason}</div>
                        )}
                      </li>
                    ))}
                  </ol>
                )}
              </div>
            </div>
          </>
        ) : null}
      </SheetContent>
    </Sheet>
  )
}
