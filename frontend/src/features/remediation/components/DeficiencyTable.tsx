import EmptyState from '@/components/illustration/EmptyState'
import { useState } from 'react'
import { Loader2, Pencil, Trash2 } from 'lucide-react'
import { toast } from 'sonner'
import { useQueryClient } from '@tanstack/react-query'
import apiClient from '@/lib/axios'
import { queryKeys } from '@/lib/queryKeys'
import { useActiveTenantId } from '@/features/auth/store'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import type { Deficiency, DeficiencyListResponse, RemediationPlan } from '../types'
import {
  SEVERITY_LABELS,
  SEVERITY_BADGE_CLASS,
  DEFICIENCY_STATUS_LABELS,
  DEFICIENCY_STATUS_BADGE_CLASS,
  APPROVAL_STATUS_LABELS,
  REMEDIATION_STATUS_LABELS,
  REMEDIATION_STATUS_BADGE_CLASS,
} from '../types'
import { useCanWrite } from '@/features/auth/useCanWrite'
import HelpButton from '@/features/help/HelpButton'

interface Props {
  data: DeficiencyListResponse | undefined
  plans: RemediationPlan[]
  onAddClick: () => void
  onEditClick: (item: Deficiency) => void
  /** 평가 결론·결재 열기 */
  onConclusionClick: (item: Deficiency) => void
  onDeleteClick: (item: Deficiency) => void
  onPlanClick: (planId: string) => void
  onCreatePlanClick: (deficiencyId: string) => void
  isLoading: boolean
  isError: boolean
  error: Error | null | unknown
}

export default function DeficiencyTable({
  data,
  plans,
  onAddClick,
  onEditClick,
  onConclusionClick,
  onDeleteClick,
  onPlanClick,
  onCreatePlanClick,
  isLoading,
  isError,
  error,
}: Props) {
  const canWrite = useCanWrite()
  const tenantId = useActiveTenantId()
  const queryClient = useQueryClient()
  // 일괄 결재(ADR-0038 2-4) — 건별로 판정되고 실패 건은 이유와 함께 돌아온다
  const [picked, setPicked] = useState<Set<string>>(new Set())
  const [bulkBusy, setBulkBusy] = useState(false)
  const toggle = (id: string) => setPicked((prev) => {
    const next = new Set(prev)
    if (next.has(id)) next.delete(id)
    else next.add(id)
    return next
  })
  const bulk = async (to: 'review' | 'confirmed') => {
    const reason = to === 'confirmed' ? window.prompt('확정 사유를 입력하세요 (필수)')?.trim() : undefined
    if (to === 'confirmed' && !reason) return
    setBulkBusy(true)
    try {
      const r = (await apiClient.post<{ succeeded: number; failed: number; items: { code: string | null; ok: boolean; detail: string | null }[] }>(
        '/api/remediation/deficiencies/bulk-transition', { ids: [...picked], to_status: to, reason: reason ?? null })).data
      const fails = r.items.filter((i) => !i.ok)
      if (r.succeeded) toast.success(`${r.succeeded}건 ${to === 'review' ? '검토 요청' : '확정'}했습니다`)
      if (fails.length) toast.error(`${fails.length}건 실패 — ${fails.slice(0, 3).map((i) => `${i.code ?? ''}: ${i.detail}`).join(' / ')}${fails.length > 3 ? ' …' : ''}`)
      setPicked(new Set())
      queryClient.invalidateQueries({ queryKey: queryKeys.remediation.deficienciesAll(tenantId) })
    } catch (e) {
      const d = (e as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
      toast.error(typeof d === 'string' ? d : '일괄 처리하지 못했습니다')
    } finally {
      setBulkBusy(false)
    }
  }
  const planMap = Object.fromEntries(plans.map((p) => [p.deficiency_id, p]))
  const { items = [], total = 0 } = data ?? {}

  if (isLoading) {
    return (
      <div className="flex items-center justify-center p-12 text-muted-foreground gap-2">
        <Loader2 className="h-5 w-5 animate-spin" />
        불러오는 중...
      </div>
    )
  }

  if (isError) {
    return (
      <div className="rounded-md border p-8 text-center text-sm text-destructive">
        데이터를 불러오지 못했습니다.{' '}
        {error instanceof Error ? error.message : '잠시 후 다시 시도해주세요.'}
      </div>
    )
  }

  if (items.length === 0) {
    return (
      <EmptyState
        slot="empty-checklist"
        title="등록된 미비점이 없습니다"
        description={canWrite ? '미비점 등록 버튼으로 첫 미비점을 추가하세요.' : undefined}
        action={canWrite ? <Button size="sm" onClick={onAddClick}>미비점 등록</Button> : undefined}
      />
    )
  }

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
        총 {total}건
        <HelpButton k="screen.remediation.deficiencies" />
        {canWrite && picked.size > 0 && (
          <span className="ml-auto flex items-center gap-2">
            선택 {picked.size}건
            <HelpButton k="screen.remediation.bulk-approval" />
            <Button size="sm" variant="outline" disabled={bulkBusy} onClick={() => bulk('review')}>일괄 검토 요청</Button>
            <Button size="sm" disabled={bulkBusy} onClick={() => bulk('confirmed')}>일괄 승인</Button>
          </span>
        )}
      </div>
      <div className="overflow-hidden rounded-xl border bg-card shadow-card">
        <Table>
          <TableHeader>
            <TableRow>
              {canWrite && <TableHead className="w-8" />}
              <TableHead>코드</TableHead>
              <TableHead>심각도</TableHead>
              <TableHead>설명</TableHead>
              <TableHead>상태</TableHead>
              <TableHead>평가 결론</TableHead>
              <TableHead>회계연도</TableHead>
              <TableHead>개선계획</TableHead>
              <TableHead className="w-20"></TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {items.map((item: Deficiency) => (
              <TableRow key={item.id}>
                {canWrite && (
                  <TableCell>
                    <input type="checkbox" aria-label={`${item.code} 선택`} checked={picked.has(item.id)}
                      disabled={item.approval_status === 'confirmed'} onChange={() => toggle(item.id)} />
                  </TableCell>
                )}
                <TableCell className="font-mono text-sm">{item.code}</TableCell>
                <TableCell>
                  <Badge variant="outline" className={SEVERITY_BADGE_CLASS[item.severity]}>
                    {SEVERITY_LABELS[item.severity]}
                  </Badge>
                </TableCell>
                <TableCell className="max-w-xs truncate text-sm">{item.description}</TableCell>
                <TableCell>
                  <Badge variant="outline" className={DEFICIENCY_STATUS_BADGE_CLASS[item.status]}>
                    {DEFICIENCY_STATUS_LABELS[item.status]}
                  </Badge>
                </TableCell>
                <TableCell>
                  <Badge variant={item.approval_status === 'confirmed' ? 'default' : 'outline'}
                    className="cursor-pointer" onClick={() => onConclusionClick(item)}>
                    {APPROVAL_STATUS_LABELS[item.approval_status]}
                  </Badge>
                </TableCell>
                <TableCell>{item.fiscal_year}</TableCell>
                <TableCell onClick={(e) => e.stopPropagation()}>
                  {planMap[item.id] ? (
                    <Badge
                      variant="outline"
                      className={`cursor-pointer ${REMEDIATION_STATUS_BADGE_CLASS[planMap[item.id].status]}`}
                      onClick={() => onPlanClick(planMap[item.id].id)}
                    >
                      {REMEDIATION_STATUS_LABELS[planMap[item.id].status]}
                    </Badge>
                  ) : canWrite && (
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-6 text-xs px-2 text-muted-foreground hover:text-foreground"
                      onClick={() => onCreatePlanClick(item.id)}
                    >
                      + 등록
                    </Button>
                  )}
                </TableCell>
                <TableCell onClick={(e) => e.stopPropagation()}>
                  {canWrite && (
                    <div className="flex items-center gap-1">
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-7 w-7"
                        onClick={() => onEditClick(item)}
                      >
                        <Pencil className="h-3.5 w-3.5" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        disabled={item.approval_status !== 'draft'}
                        title={item.approval_status !== 'draft' ? '검토 중·확정된 미비점은 삭제할 수 없습니다' : undefined}
                        className="h-7 w-7 hover:bg-red-50 hover:text-red-600"
                        onClick={() => onDeleteClick(item)}
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </Button>
                    </div>
                  )}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  )
}
