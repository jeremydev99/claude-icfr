import { Loader2 } from 'lucide-react'
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
import type { RemediationPlan, RemediationPlanListResponse } from '../types'
import {
  REMEDIATION_STATUS_LABELS,
  REMEDIATION_STATUS_BADGE_CLASS,
  PRIORITY_LABELS,
  PRIORITY_BADGE_CLASS,
} from '../types'

interface Props {
  data: RemediationPlanListResponse | undefined
  onAddClick: () => void
  onRowClick?: (id: string) => void
  isLoading: boolean
  isError: boolean
  error: Error | null | unknown
}

function formatDate(dateStr: string | null | undefined): string {
  if (!dateStr) return '—'
  return dateStr.slice(0, 10)
}

export default function RemediationPlanTable({
  data,
  onAddClick,
  onRowClick,
  isLoading,
  isError,
  error,
}: Props) {
  const { items = [], total = 0 } = data ?? {}

  if (isLoading) {
    return (
      <div className="flex justify-center items-center py-20">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
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
      <div className="rounded-md border p-12 text-center text-sm text-muted-foreground">
        등록된 개선계획이 없습니다.{' '}
        <button
          className="underline underline-offset-2 hover:text-foreground"
          onClick={onAddClick}
        >
          개선계획 등록
        </button>{' '}
        버튼으로 첫 계획을 추가하세요.
      </div>
    )
  }

  return (
    <div className="space-y-2">
      <div className="text-sm text-muted-foreground">총 {total}건</div>
      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>개선 조치</TableHead>
              <TableHead>우선순위</TableHead>
              <TableHead>상태</TableHead>
              <TableHead>담당자 ID</TableHead>
              <TableHead>목표일</TableHead>
              <TableHead className="w-16"></TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {items.map((plan: RemediationPlan) => (
              <TableRow
                key={plan.id}
                className="cursor-pointer hover:bg-muted/30"
                onClick={() => onRowClick?.(plan.id)}
              >
                <TableCell className="max-w-xs truncate text-sm">{plan.action_plan}</TableCell>
                <TableCell>
                  <Badge variant="outline" className={PRIORITY_BADGE_CLASS[plan.priority]}>
                    {PRIORITY_LABELS[plan.priority]}
                  </Badge>
                </TableCell>
                <TableCell>
                  <Badge variant="outline" className={REMEDIATION_STATUS_BADGE_CLASS[plan.status]}>
                    {REMEDIATION_STATUS_LABELS[plan.status]}
                  </Badge>
                </TableCell>
                <TableCell className="font-mono text-xs text-muted-foreground">
                  {plan.owner_id.slice(0, 8)}...
                </TableCell>
                <TableCell>{formatDate(plan.target_date)}</TableCell>
                <TableCell onClick={(e) => e.stopPropagation()}>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => onRowClick?.(plan.id)}
                  >
                    상세
                  </Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  )
}
