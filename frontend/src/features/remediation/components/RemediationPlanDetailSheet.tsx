import { Loader2 } from 'lucide-react'
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
import { usePlanDetail, useTransitionPlan, usePlanHistory } from '../api/useRemediationPlans'
import { useDeficiencies } from '../api/useDeficiencies'
import { useUsers } from '@/features/users/api/useUsers'
import {
  REMEDIATION_STATUS_LABELS,
  REMEDIATION_STATUS_BADGE_CLASS,
  PRIORITY_LABELS,
  PRIORITY_BADGE_CLASS,
  type RemediationStatus,
} from '../types'

interface Props {
  planId: string | null
  open: boolean
  onOpenChange: (open: boolean) => void
}

const NEXT_TRANSITION: Record<
  RemediationStatus,
  { label: string; to_status: 'in_progress' | 'completed' | 'approved' } | null
> = {
  planned: { label: '진행 시작', to_status: 'in_progress' },
  in_progress: { label: '완료 처리', to_status: 'completed' },
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

export default function RemediationPlanDetailSheet({ planId, open, onOpenChange }: Props) {
  const { data: plan, isLoading } = usePlanDetail(planId)
  const { data: historyData } = usePlanHistory(planId)
  const transition = useTransitionPlan()

  const { data: deficienciesData } = useDeficiencies({ limit: 200 })
  const { data: usersData } = useUsers({ limit: 200 })

  const deficiencyMap = Object.fromEntries(
    (deficienciesData?.items ?? []).map((d) => [d.id, d])
  )
  const userMap = Object.fromEntries(
    (usersData?.items ?? []).map((u) => [u.id, u])
  )

  const deficiencyLabel = (id: string) => deficiencyMap[id]?.code ?? id.slice(0, 8) + '...'
  const ownerLabel = (id: string) => {
    const u = userMap[id]
    return u ? u.display_name : id.slice(0, 8) + '...'
  }

  const nextTrans = plan ? NEXT_TRANSITION[plan.status] : null

  const handleTransition = () => {
    if (!plan || !nextTrans) return
    transition.mutate(
      { id: plan.id, payload: { to_status: nextTrans.to_status } },
      {
        onSuccess: () =>
          toast.success(`상태가 '${REMEDIATION_STATUS_LABELS[nextTrans.to_status]}'로 변경되었습니다`),
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
        ) : plan ? (
          <>
            <SheetHeader className="pr-2">
              <div className="flex items-start justify-between gap-2">
                <div className="space-y-0.5 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <SheetTitle className="text-xl font-bold">개선계획 상세</SheetTitle>
                    <Badge variant="outline" className={REMEDIATION_STATUS_BADGE_CLASS[plan.status]}>
                      {REMEDIATION_STATUS_LABELS[plan.status]}
                    </Badge>
                    <Badge variant="outline" className={PRIORITY_BADGE_CLASS[plan.priority]}>
                      {PRIORITY_LABELS[plan.priority]}
                    </Badge>
                  </div>
                </div>
              </div>
            </SheetHeader>

            <div className="mt-4 space-y-1">
              {/* 섹션 1 — 기본 정보 */}
              <SectionTitle>기본 정보</SectionTitle>
              <Separator />
              <InfoRow label="미비점" value={
                <span className="font-mono text-sm">{deficiencyLabel(plan.deficiency_id)}</span>
              } />
              <InfoRow label="담당자" value={ownerLabel(plan.owner_id)} />
              <InfoRow label="목표일" value={plan.target_date?.slice(0, 10)} />
              <InfoRow label="개선 조치" value={
                <span className="whitespace-pre-wrap">{plan.action_plan}</span>
              } />
              {plan.improvement_description && (
                <InfoRow label="개선 내용" value={
                  <span className="whitespace-pre-wrap">{plan.improvement_description}</span>
                } />
              )}
              {plan.owner_opinion && (
                <InfoRow label="담당자 의견" value={
                  <span className="whitespace-pre-wrap">{plan.owner_opinion}</span>
                } />
              )}
              {plan.reviewer_opinion && (
                <InfoRow label="검토자 의견" value={
                  <span className="whitespace-pre-wrap">{plan.reviewer_opinion}</span>
                } />
              )}
              {plan.approved_at && (
                <InfoRow label="승인일" value={plan.approved_at.slice(0, 10)} />
              )}

              {/* 섹션 2 — 워크플로 */}
              <SectionTitle>워크플로</SectionTitle>
              <Separator />
              <div className="py-2">
                {nextTrans ? (
                  <Button size="sm" onClick={handleTransition} disabled={transition.isPending}>
                    {transition.isPending && (
                      <Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" />
                    )}
                    {nextTrans.label}
                  </Button>
                ) : (
                  <span className="text-sm text-muted-foreground">최종 승인 완료</span>
                )}
              </div>

              {/* 섹션 3 — 상태 이력 */}
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
                            ? `${REMEDIATION_STATUS_LABELS[h.from_status]} → `
                            : ''}
                          {REMEDIATION_STATUS_LABELS[h.to_status]}
                        </div>
                        <div className="text-xs text-muted-foreground mt-0.5">
                          {h.changed_by?.display_name ?? h.changed_by_id.slice(0, 8)} · {h.changed_at.slice(0, 10)}
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
