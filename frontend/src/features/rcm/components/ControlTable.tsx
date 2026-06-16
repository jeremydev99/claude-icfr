import { ChevronUp, ChevronDown, ChevronsUpDown, Star, Pencil, Trash2, Upload, Loader2 } from 'lucide-react'
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
import type { Control, ControlListResponse, ControlSearchParams } from '../types'
import {
  AUTO_MANUAL_LABELS,
  FREQUENCY_LABELS,
  PD_LABELS,
  RISK_LEVEL_LABELS,
} from '../types'

interface Props {
  data: ControlListResponse | undefined
  params: ControlSearchParams
  onParamsChange: (updated: Partial<ControlSearchParams>) => void
  onSelect?: (control: Control) => void
  onAddClick?: () => void
  onEdit?: (control: Control) => void
  onDelete?: (control: Control) => void
  onUploadClick?: () => void
  isLoading?: boolean
  isError?: boolean
  error?: Error | null
}

const RISK_BADGE_VARIANT: Record<string, string> = {
  SR: 'bg-red-100 text-red-700 border-red-200',
  HR: 'bg-orange-100 text-orange-700 border-orange-200',
  MR: 'bg-yellow-100 text-yellow-700 border-yellow-200',
  LR: 'bg-green-100 text-green-700 border-green-200',
}

type SortCol = 'code' | 'name' | 'frequency' | 'owner_name'

function SortIcon({ col, params }: { col: SortCol; params: ControlSearchParams }) {
  if (params.sort_by !== col) return <ChevronsUpDown className="ml-1 h-3 w-3 opacity-40" />
  return params.sort_order === 'asc' ? (
    <ChevronUp className="ml-1 h-3 w-3" />
  ) : (
    <ChevronDown className="ml-1 h-3 w-3" />
  )
}

export default function ControlTable({ data, params, onParamsChange, onSelect, onAddClick, onEdit, onDelete, onUploadClick, isLoading, isError, error }: Props) {
  const { items = [], total = 0, skip = 0, limit = params.limit ?? 20 } = data ?? {}

  const toggleSort = (col: SortCol) => {
    if (params.sort_by === col) {
      onParamsChange({ sort_order: params.sort_order === 'asc' ? 'desc' : 'asc', skip: 0 })
    } else {
      onParamsChange({ sort_by: col, sort_order: 'asc', skip: 0 })
    }
  }

  const page = Math.floor(skip / limit)
  const totalPages = Math.ceil(total / limit)
  const from = total === 0 ? 0 : skip + 1
  const to = Math.min(skip + limit, total)

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
      <div className="rounded-md border border-red-200 bg-red-50 p-6 text-red-700 text-sm">
        불러오기 실패: {error?.message ?? '알 수 없는 오류'}
        <br />
        백엔드가 실행 중인지, 로그인 상태인지 확인해주세요.
      </div>
    )
  }

  return (
    <div className="space-y-2">
      <div className="flex justify-end gap-2">
        <Button variant="outline" size="sm" onClick={onUploadClick}>
          <Upload className="h-4 w-4 mr-1.5" />
          Excel 업로드
        </Button>
        <Button size="sm" onClick={onAddClick}>
          + 통제 추가
        </Button>
      </div>
      <div className="rounded-md border overflow-x-auto">
        <Table>
          <TableHeader>
            <TableRow className="bg-muted/50">
              <TableHead
                className="w-32 cursor-pointer select-none whitespace-nowrap"
                onClick={() => toggleSort('code')}
              >
                <span className="flex items-center">
                  통제코드 <SortIcon col="code" params={params} />
                </span>
              </TableHead>
              <TableHead
                className="min-w-48 cursor-pointer select-none"
                onClick={() => toggleSort('name')}
              >
                <span className="flex items-center">
                  통제명 <SortIcon col="name" params={params} />
                </span>
              </TableHead>
              <TableHead className="w-20">프로세스</TableHead>
              <TableHead className="w-20">위험수준</TableHead>
              <TableHead className="w-20">핵심통제</TableHead>
              <TableHead className="w-20">예방/적발</TableHead>
              <TableHead className="w-24">자동/수동</TableHead>
              <TableHead
                className="w-16 cursor-pointer select-none"
                onClick={() => toggleSort('frequency')}
              >
                <span className="flex items-center">
                  주기 <SortIcon col="frequency" params={params} />
                </span>
              </TableHead>
              <TableHead className="w-36">어서션</TableHead>
              <TableHead
                className="w-24 cursor-pointer select-none"
                onClick={() => toggleSort('owner_name')}
              >
                <span className="flex items-center">
                  담당자 <SortIcon col="owner_name" params={params} />
                </span>
              </TableHead>
              <TableHead className="w-20"></TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {items.length === 0 ? (
              <TableRow>
                <TableCell colSpan={11} className="h-32 text-center text-muted-foreground">
                  검색 결과가 없습니다
                </TableCell>
              </TableRow>
            ) : (
              items.map((ctrl: Control) => (
                <TableRow key={ctrl.id} className="group hover:bg-muted/30 cursor-pointer" onClick={() => onSelect?.(ctrl)}>
                  <TableCell className="font-mono text-xs font-medium text-blue-600 whitespace-nowrap hover:underline cursor-pointer">
                    {ctrl.code}
                  </TableCell>
                  <TableCell className="text-sm">{ctrl.name}</TableCell>
                  <TableCell>
                    {ctrl.process_code ? (
                      <Badge variant="outline" className="text-xs">
                        {ctrl.process_code}
                      </Badge>
                    ) : (
                      <span className="text-muted-foreground text-xs">—</span>
                    )}
                  </TableCell>
                  <TableCell>
                    {ctrl.risk_level ? (
                      <span
                        className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium ${RISK_BADGE_VARIANT[ctrl.risk_level]}`}
                      >
                        {RISK_LEVEL_LABELS[ctrl.risk_level]}
                      </span>
                    ) : (
                      <span className="text-muted-foreground text-xs">—</span>
                    )}
                  </TableCell>
                  <TableCell>
                    {ctrl.is_key_control ? (
                      <span className="inline-flex items-center gap-0.5 text-amber-600 text-xs font-medium">
                        <Star className="h-3 w-3 fill-amber-500 text-amber-500" />
                        핵심
                      </span>
                    ) : (
                      <span className="text-muted-foreground text-xs">—</span>
                    )}
                  </TableCell>
                  <TableCell className="text-xs">{PD_LABELS[ctrl.preventive_detective]}</TableCell>
                  <TableCell className="text-xs">{AUTO_MANUAL_LABELS[ctrl.auto_manual]}</TableCell>
                  <TableCell className="text-xs">{FREQUENCY_LABELS[ctrl.frequency]}</TableCell>
                  <TableCell>
                    <div className="flex flex-wrap gap-0.5">
                      {(ctrl.assertions ?? []).map((a) => (
                        <Badge key={a} variant="secondary" className="text-xs px-1.5 py-0">
                          {a}
                        </Badge>
                      ))}
                    </div>
                  </TableCell>
                  <TableCell className="text-xs text-muted-foreground">
                    {ctrl.owner_name ? ctrl.owner_name.split(/[\s,]+/).filter(Boolean).join(', ') : '—'}
                  </TableCell>
                  <TableCell onClick={(e) => e.stopPropagation()} className="text-right pr-2">
                    <div className="flex items-center justify-end gap-0.5 opacity-0 group-hover:opacity-100">
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-7 w-7"
                        onClick={() => onEdit?.(ctrl)}
                        title="편집"
                      >
                        <Pencil className="h-3.5 w-3.5" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-7 w-7 hover:bg-red-50 hover:text-red-600"
                        onClick={() => onDelete?.(ctrl)}
                        title="삭제"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      <div className="flex items-center justify-between px-1 text-sm text-muted-foreground">
        <span>
          전체 {total}건 중 {from}–{to}
        </span>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5">
            <span>페이지당</span>
            <Select
              value={String(limit)}
              onValueChange={(v) => onParamsChange({ limit: Number(v), skip: 0 })}
            >
              <SelectTrigger className="h-8 w-20">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="20">20</SelectItem>
                <SelectItem value="50">50</SelectItem>
                <SelectItem value="100">100</SelectItem>
              </SelectContent>
            </Select>
            <span>개</span>
          </div>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              disabled={page === 0}
              onClick={() => onParamsChange({ skip: (page - 1) * limit })}
            >
              이전
            </Button>
            <Button
              variant="outline"
              size="sm"
              disabled={page >= totalPages - 1}
              onClick={() => onParamsChange({ skip: (page + 1) * limit })}
            >
              다음
            </Button>
          </div>
        </div>
      </div>
    </div>
  )
}
