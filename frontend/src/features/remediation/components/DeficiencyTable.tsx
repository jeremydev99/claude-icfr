import { Loader2, Pencil, Trash2 } from 'lucide-react'
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
  REMEDIATION_STATUS_LABELS,
  REMEDIATION_STATUS_BADGE_CLASS,
} from '../types'

interface Props {
  data: DeficiencyListResponse | undefined
  plans: RemediationPlan[]
  onAddClick: () => void
  onEditClick: (item: Deficiency) => void
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
  onDeleteClick,
  onPlanClick,
  onCreatePlanClick,
  isLoading,
  isError,
  error,
}: Props) {
  const planMap = Object.fromEntries(plans.map((p) => [p.deficiency_id, p]))
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
        등록된 미비점이 없습니다.{' '}
        <button
          className="underline underline-offset-2 hover:text-foreground"
          onClick={onAddClick}
        >
          미비점 등록
        </button>{' '}
        버튼으로 첫 미비점을 추가하세요.
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
              <TableHead>코드</TableHead>
              <TableHead>심각도</TableHead>
              <TableHead>설명</TableHead>
              <TableHead>상태</TableHead>
              <TableHead>회계연도</TableHead>
              <TableHead>개선계획</TableHead>
              <TableHead className="w-20"></TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {items.map((item: Deficiency) => (
              <TableRow key={item.id}>
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
                  ) : (
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
                      className="h-7 w-7 hover:bg-red-50 hover:text-red-600"
                      onClick={() => onDeleteClick(item)}
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </Button>
                  </div>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  )
}
