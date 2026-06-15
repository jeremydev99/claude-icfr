import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Button } from '@/components/ui/button'
import { Plus } from 'lucide-react'
import type { TestRunSearchParams, TestRunStatus } from '../types'
import { STATUS_LABELS } from '../types'

interface Props {
  value: TestRunSearchParams
  onChange: (updated: Partial<TestRunSearchParams>) => void
  onAddClick: () => void
}

const currentYear = new Date().getFullYear()
const YEAR_OPTIONS = [
  currentYear - 2,
  currentYear - 1,
  currentYear,
  currentYear + 1,
]

const STATUS_OPTIONS: Array<{ value: TestRunStatus | 'all'; label: string }> = [
  { value: 'all', label: '전체' },
  { value: 'planned', label: STATUS_LABELS.planned },
  { value: 'in_progress', label: STATUS_LABELS.in_progress },
  { value: 'completed', label: STATUS_LABELS.completed },
  { value: 'approved', label: STATUS_LABELS.approved },
]

export default function TestRunSearchBar({ value, onChange, onAddClick }: Props) {
  return (
    <div className="flex items-center gap-3">
      <Select
        value={String(value.fiscal_year ?? currentYear)}
        onValueChange={(v) => onChange({ fiscal_year: Number(v), skip: 0 })}
      >
        <SelectTrigger className="w-28">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {YEAR_OPTIONS.map((y) => (
            <SelectItem key={y} value={String(y)}>
              {y}년
            </SelectItem>
          ))}
        </SelectContent>
      </Select>

      <Select
        value={value.status_filter ?? 'all'}
        onValueChange={(v) =>
          onChange({
            status_filter: v === 'all' ? undefined : (v as TestRunStatus),
            skip: 0,
          })
        }
      >
        <SelectTrigger className="w-36">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {STATUS_OPTIONS.map((opt) => (
            <SelectItem key={opt.value} value={opt.value}>
              {opt.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>

      <div className="ml-auto">
        <Button onClick={onAddClick}>
          <Plus className="mr-1 h-4 w-4" />
          평가 추가
        </Button>
      </div>
    </div>
  )
}
