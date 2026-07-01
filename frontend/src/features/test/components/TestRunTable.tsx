import { Loader2 } from 'lucide-react'
import { formatDate } from '@/lib/utils'
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import type { TestRun, TestRunListResponse, TestRunSearchParams } from '../types'
import {
  STATUS_LABELS,
  STATUS_BADGE_CLASS,
  RESULT_LABELS,
  RESULT_BADGE_CLASS,
} from '../types'
import type { Control } from '@/features/rcm/types'

interface Props {
  data: TestRunListResponse | undefined
  controlMap: Record<string, Control>
  params: TestRunSearchParams
  onParamsChange: (updated: Partial<TestRunSearchParams>) => void
  onAddClick: () => void
  onRowClick?: (id: string) => void
  isLoading: boolean
  isError: boolean
  error: Error | null | unknown
}


export default function TestRunTable({
  data,
  controlMap,
  params,
  onParamsChange,
  onAddClick,
  onRowClick,
  isLoading,
  isError,
  error,
}: Props) {
  const { items = [], total = 0, skip = 0, limit = params.limit ?? 20 } = data ?? {}

  const currentPage = Math.floor(skip / limit) + 1
  const totalPages = Math.max(1, Math.ceil(total / limit))

  const handlePage = (page: number) => {
    onParamsChange({ skip: (page - 1) * limit })
  }

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
      <div className="rounded-md border p-12 text-center text-sm text-muted-foreground">
        등록된 평가가 없습니다.{' '}
        <button
          className="underline underline-offset-2 hover:text-foreground"
          onClick={onAddClick}
        >
          평가 추가
        </button>{' '}
        버튼으로 첫 평가를 만들어주세요.
      </div>
    )
  }

  return (
    <div className="space-y-2">
      <div className="text-sm text-muted-foreground">
        총 {total}건
      </div>

      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>통제코드</TableHead>
              <TableHead>통제명</TableHead>
              <TableHead>평가연도</TableHead>
              <TableHead>상태</TableHead>
              <TableHead>결과</TableHead>
              <TableHead>평가일</TableHead>
              <TableHead>평가자</TableHead>
              <TableHead className="w-16"></TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {items.map((run: TestRun) => {
              const ctrl = controlMap[run.control_id]
              return (
                <TableRow
                  key={run.id}
                  className="cursor-pointer hover:bg-muted/30"
                  onClick={() => onRowClick?.(run.id)}
                >
                  <TableCell className="font-mono text-sm">{ctrl?.code ?? '—'}</TableCell>
                  <TableCell className="max-w-xs truncate">{ctrl?.name ?? run.control_id.slice(0, 8) + '...'}</TableCell>
                  <TableCell>{run.fiscal_year}</TableCell>
                  <TableCell>
                    <Badge
                      variant="outline"
                      className={STATUS_BADGE_CLASS[run.status]}
                    >
                      {STATUS_LABELS[run.status]}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    {run.result ? (
                      <Badge
                        variant="outline"
                        className={RESULT_BADGE_CLASS[run.result]}
                      >
                        {RESULT_LABELS[run.result]}
                      </Badge>
                    ) : (
                      <span className="text-muted-foreground">—</span>
                    )}
                  </TableCell>
                  <TableCell>{formatDate(run.test_date)}</TableCell>
                  <TableCell className="text-muted-foreground">—</TableCell>
                  <TableCell onClick={(e) => e.stopPropagation()}>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => onRowClick?.(run.id)}
                    >
                      상세
                    </Button>
                  </TableCell>
                </TableRow>
              )
            })}
          </TableBody>
        </Table>
      </div>

      {totalPages > 1 && (
        <div className="flex items-center justify-between pt-1">
          <span className="text-sm text-muted-foreground">
            {currentPage} / {totalPages} 페이지
          </span>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => handlePage(currentPage - 1)}
              disabled={currentPage <= 1}
            >
              이전
            </Button>
            <Select
              value={String(limit)}
              onValueChange={(v) => onParamsChange({ limit: Number(v), skip: 0 })}
            >
              <SelectTrigger className="w-20 h-8 text-sm">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {[10, 20, 50].map((n) => (
                  <SelectItem key={n} value={String(n)}>
                    {n}건
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Button
              variant="outline"
              size="sm"
              onClick={() => handlePage(currentPage + 1)}
              disabled={currentPage >= totalPages}
            >
              다음
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}
