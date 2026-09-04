import { Loader2, Pencil, Trash2 } from 'lucide-react'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Button } from '@/components/ui/button'
import type { ProcessItem, SubProcessItem } from '../../types'
import SourceBadge from '../SourceBadge'
import { canEditHierarchy } from '../../permissions'

interface Props {
  items: SubProcessItem[]
  processes: ProcessItem[]
  isLoading: boolean
  isError: boolean
  error: Error | null | unknown
  onEditClick: (item: SubProcessItem) => void
  onDeleteClick: (item: SubProcessItem) => void
}

export default function SubProcessTable({
  items,
  processes,
  isLoading,
  isError,
  error,
  onEditClick,
  onDeleteClick,
}: Props) {
  const canEdit = canEditHierarchy()
  const processCodeById = new Map(processes.map((p) => [p.id, p.code]))

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
        등록된 세부 프로세스가 없습니다. 세부 프로세스 추가 버튼으로 첫 항목을 등록하세요.
      </div>
    )
  }

  return (
    <div className="space-y-2">
      <div className="text-sm text-muted-foreground">총 {items.length}건</div>
      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-32">코드</TableHead>
              <TableHead>세부 프로세스명</TableHead>
              <TableHead className="w-28">상위 프로세스</TableHead>
              <TableHead className="w-20">구분</TableHead>
              <TableHead className="w-20"></TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {items.map((item) => (
              <TableRow key={item.id}>
                <TableCell className="font-mono text-sm">{item.code}</TableCell>
                <TableCell className="font-medium">{item.name}</TableCell>
                <TableCell className="text-sm text-muted-foreground">
                  {processCodeById.get(item.process_id) ?? '—'}
                </TableCell>
                <TableCell>
                  <SourceBadge envelope={item.envelope} />
                </TableCell>
                <TableCell>
                  {canEdit && (
                    <div className="flex items-center gap-1">
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-7 w-7"
                        title="편집"
                        onClick={() => onEditClick(item)}
                      >
                        <Pencil className="h-3.5 w-3.5" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-7 w-7 hover:bg-red-50 hover:text-red-600"
                        title="삭제"
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
