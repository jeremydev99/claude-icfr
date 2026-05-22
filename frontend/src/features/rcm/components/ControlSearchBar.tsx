import { useCallback, useRef, useState } from 'react'
import { Search, SlidersHorizontal, X } from 'lucide-react'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Checkbox } from '@/components/ui/checkbox'
import { Label } from '@/components/ui/label'
import type { AutoManual, ControlSearchParams, Frequency, PreventiveDetective, RiskLevel } from '../types'
import {
  AUTO_MANUAL_LABELS,
  ASSERTION_LABELS,
  FREQUENCY_LABELS,
  PD_LABELS,
  RISK_LEVEL_LABELS,
} from '../types'
import type { AssertionCode } from '../types'

interface Props {
  params: ControlSearchParams
  onChange: (updated: Partial<ControlSearchParams>) => void
  onReset: () => void
}

const PROCESSES = ['O2C', 'P2P', 'R2R', 'HR', 'ITG']

export default function ControlSearchBar({ params, onChange, onReset }: Props) {
  const [open, setOpen] = useState(false)
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const handleTextChange = useCallback(
    (value: string) => {
      if (debounceRef.current) clearTimeout(debounceRef.current)
      debounceRef.current = setTimeout(() => {
        onChange({ q: value || undefined, skip: 0 })
      }, 300)
    },
    [onChange],
  )

  const sel = <T extends string>(
    value: T | undefined,
    onValueChange: (v: T | undefined) => void,
    placeholder: string,
    options: [T, string][],
  ) => (
    <Select
      value={value ?? '__all__'}
      onValueChange={(v) => onValueChange(v === '__all__' ? undefined : (v as T))}
    >
      <SelectTrigger className="h-8 w-36 text-xs">
        <SelectValue placeholder={placeholder} />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value="__all__">전체</SelectItem>
        {options.map(([k, label]) => (
          <SelectItem key={k} value={k}>
            {label}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  )

  return (
    <div className="rounded-lg border bg-white p-3 space-y-2">
      <div className="flex gap-2">
        <div className="relative flex-1">
          <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input
            className="pl-8 h-9"
            placeholder="통제코드·통제명·담당자 검색..."
            defaultValue={params.q ?? ''}
            onChange={(e) => handleTextChange(e.target.value)}
          />
        </div>
        <Button
          variant="outline"
          size="sm"
          className="gap-1 h-9"
          onClick={() => setOpen((p) => !p)}
        >
          <SlidersHorizontal className="h-4 w-4" />
          필터
        </Button>
        <Button variant="ghost" size="sm" className="gap-1 h-9 text-muted-foreground" onClick={onReset}>
          <X className="h-3 w-3" />
          초기화
        </Button>
      </div>

      {open && (
        <div className="pt-1 grid grid-cols-2 md:grid-cols-3 gap-x-4 gap-y-2">
          <div className="space-y-1">
            <Label className="text-xs text-muted-foreground">프로세스</Label>
            {sel(
              params.process_code,
              (v) => onChange({ process_code: v, skip: 0 }),
              '전체',
              PROCESSES.map((p) => [p, p] as [string, string]),
            )}
          </div>

          <div className="space-y-1">
            <Label className="text-xs text-muted-foreground">위험수준</Label>
            {sel<RiskLevel>(
              params.risk_level,
              (v) => onChange({ risk_level: v, skip: 0 }),
              '전체',
              Object.entries(RISK_LEVEL_LABELS) as [RiskLevel, string][],
            )}
          </div>

          <div className="space-y-1">
            <Label className="text-xs text-muted-foreground">주기</Label>
            {sel<Frequency>(
              params.frequency,
              (v) => onChange({ frequency: v, skip: 0 }),
              '전체',
              Object.entries(FREQUENCY_LABELS) as [Frequency, string][],
            )}
          </div>

          <div className="space-y-1">
            <Label className="text-xs text-muted-foreground">자동/수동</Label>
            {sel<AutoManual>(
              params.auto_manual,
              (v) => onChange({ auto_manual: v, skip: 0 }),
              '전체',
              Object.entries(AUTO_MANUAL_LABELS) as [AutoManual, string][],
            )}
          </div>

          <div className="space-y-1">
            <Label className="text-xs text-muted-foreground">예방/적발</Label>
            {sel<PreventiveDetective>(
              params.preventive_detective,
              (v) => onChange({ preventive_detective: v, skip: 0 }),
              '전체',
              Object.entries(PD_LABELS) as [PreventiveDetective, string][],
            )}
          </div>

          <div className="space-y-1">
            <Label className="text-xs text-muted-foreground">어서션</Label>
            {sel<AssertionCode>(
              params.assertion,
              (v) => onChange({ assertion: v, skip: 0 }),
              '전체',
              Object.entries(ASSERTION_LABELS) as [AssertionCode, string][],
            )}
          </div>

          <div className="col-span-2 md:col-span-3 flex items-center gap-2 pt-1">
            <Checkbox
              id="key-only"
              checked={params.is_key_control === true}
              onCheckedChange={(checked) =>
                onChange({ is_key_control: checked === true ? true : undefined, skip: 0 })
              }
            />
            <Label htmlFor="key-only" className="text-sm cursor-pointer">
              핵심통제만 보기
            </Label>
          </div>
        </div>
      )}
    </div>
  )
}
