import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import type { ExcelPreviewItem } from '../api/uploadExcel'

interface Props {
  items: ExcelPreviewItem[]
}

export default function ExcelPreviewTable({ items }: Props) {
  if (items.length === 0) {
    return (
      <p className="text-sm text-muted-foreground text-center py-6">표시할 항목 없음</p>
    )
  }

  return (
    <div className="rounded-md border overflow-x-auto max-h-64 overflow-y-auto">
      <Table>
        <TableHeader className="sticky top-0 bg-background z-10">
          <TableRow className="bg-muted/50">
            <TableHead className="w-10">#</TableHead>
            <TableHead className="w-36">통제 코드</TableHead>
            <TableHead className="min-w-48">통제명</TableHead>
            <TableHead className="w-16">프로세스</TableHead>
            <TableHead className="w-20">위험</TableHead>
            <TableHead className="w-20">위험수준</TableHead>
            <TableHead className="w-16">예방/적발</TableHead>
            <TableHead className="w-16">자동/수동</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {items.map((item, idx) => (
            <TableRow key={idx} className="text-xs">
              <TableCell className="text-muted-foreground">{idx + 1}</TableCell>
              <TableCell className="font-mono font-medium text-blue-600">{item.code}</TableCell>
              <TableCell>{item.name}</TableCell>
              <TableCell>{item.risk_code.split('-').slice(0, 1).join('') || '—'}</TableCell>
              <TableCell className="font-mono text-xs">{item.risk_code}</TableCell>
              <TableCell>
                <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium border ${RISK_BADGE[item.is_key_control ? 'key' : 'normal']}`}>
                  {item.is_key_control ? '핵심' : '일반'}
                </span>
              </TableCell>
              <TableCell>{item.preventive_detective === 'P' ? '예방' : '적발'}</TableCell>
              <TableCell>{AM_LABEL[item.auto_manual] ?? item.auto_manual}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}

const RISK_BADGE: Record<string, string> = {
  key: 'bg-amber-100 text-amber-700 border-amber-200',
  normal: 'bg-gray-100 text-gray-600 border-gray-200',
}

const AM_LABEL: Record<string, string> = {
  A: '자동',
  M: '수동',
  IT: 'IT의존',
}
