import { Controller, useFormContext } from 'react-hook-form'
import { Label } from '@/components/ui/label'
import { Checkbox } from '@/components/ui/checkbox'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import type { ControlFormData } from '../ControlFormDialog'

const PD_OPTIONS = [
  { value: 'P', label: '예방 (Preventive)' },
  { value: 'D', label: '적발 (Detective)' },
]

const AM_OPTIONS = [
  { value: 'A', label: '자동 (Automated)' },
  { value: 'M', label: '수동 (Manual)' },
  { value: 'IT', label: 'IT의존수동 (IT-dependent)' },
]

const FREQUENCY_OPTIONS = [
  { value: 'O', label: '수시' },
  { value: 'D', label: '일' },
  { value: 'W', label: '주' },
  { value: 'M', label: '월' },
  { value: 'Q', label: '분기' },
  { value: 'A', label: '연' },
]

const IPE_OPTIONS = [
  { value: 'Y', label: '예 (Y)' },
  { value: 'N', label: '아니오 (N)' },
  { value: 'N/A', label: '해당없음 (N/A)' },
]

const ASSERTIONS = [
  { code: 'E', label: 'E — 실재성' },
  { code: 'C', label: 'C — 완전성' },
  { code: 'R', label: 'R — 권리와의무' },
  { code: 'V', label: 'V — 평가' },
  { code: 'P', label: 'P — 표시와공시' },
  { code: 'O', label: 'O — 발생' },
  { code: 'M', label: 'M — 기타' },
] as const

type AssertionCode = 'E' | 'C' | 'R' | 'V' | 'P' | 'O' | 'M'

export default function ClassificationTab() {
  const { control, watch, setValue } = useFormContext<ControlFormData>()
  const assertions = watch('assertions')

  const toggleAssertion = (code: AssertionCode) => {
    const next = assertions.includes(code)
      ? assertions.filter((a) => a !== code)
      : [...assertions, code]
    setValue('assertions', next, { shouldDirty: true })
  }

  return (
    <div className="space-y-5 py-2">
      <div className="flex items-center gap-3">
        <Controller
          name="is_key_control"
          control={control}
          render={({ field }) => (
            <Checkbox
              id="is_key_control"
              checked={field.value}
              onCheckedChange={field.onChange}
            />
          )}
        />
        <Label htmlFor="is_key_control" className="font-medium cursor-pointer">
          핵심통제 (Key Control)
        </Label>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-1.5">
          <Label>예방/적발</Label>
          <Controller
            name="preventive_detective"
            control={control}
            render={({ field }) => (
              <Select value={field.value} onValueChange={field.onChange}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  {PD_OPTIONS.map((o) => (
                    <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}
          />
        </div>

        <div className="space-y-1.5">
          <Label>자동/수동</Label>
          <Controller
            name="auto_manual"
            control={control}
            render={({ field }) => (
              <Select value={field.value} onValueChange={field.onChange}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  {AM_OPTIONS.map((o) => (
                    <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}
          />
        </div>

        <div className="space-y-1.5">
          <Label>수행 주기</Label>
          <Controller
            name="frequency"
            control={control}
            render={({ field }) => (
              <Select value={field.value} onValueChange={field.onChange}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  {FREQUENCY_OPTIONS.map((o) => (
                    <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}
          />
        </div>

        <div className="space-y-1.5">
          <Label>IPE 관련성</Label>
          <Controller
            name="ipe_relevant"
            control={control}
            render={({ field }) => (
              <Select value={field.value} onValueChange={field.onChange}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  {IPE_OPTIONS.map((o) => (
                    <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}
          />
        </div>
      </div>

      <div className="space-y-2">
        <Label>어서션 (복수 선택 가능)</Label>
        <div className="grid grid-cols-2 gap-2">
          {ASSERTIONS.map(({ code, label }) => (
            <div key={code} className="flex items-center gap-2">
              <Checkbox
                id={`assertion-${code}`}
                checked={assertions.includes(code as AssertionCode)}
                onCheckedChange={() => toggleAssertion(code as AssertionCode)}
              />
              <Label htmlFor={`assertion-${code}`} className="cursor-pointer font-normal">
                {label}
              </Label>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
