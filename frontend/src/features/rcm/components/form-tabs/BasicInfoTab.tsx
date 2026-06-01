import { Controller, useFormContext } from 'react-hook-form'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import type { ControlFormData } from '../ControlFormDialog'

const PROCESS_CODES = ['O2C', 'P2P', 'R2R', 'HR', 'ITG'] as const

const SUB_PROCESS_MAP: Record<string, string[]> = {
  O2C: ['O2C-AR', 'O2C-REV', 'O2C-COL', 'O2C-CR', 'O2C-INV'],
  P2P: ['P2P-PO', 'P2P-AP', 'P2P-INV', 'P2P-PAY', 'P2P-VEND'],
  R2R: ['R2R-GL', 'R2R-CLOSE', 'R2R-FA', 'R2R-TAX'],
  HR: ['HR-PAY', 'HR-REC', 'HR-TERM'],
  ITG: ['ITG-ACC', 'ITG-BCP', 'ITG-CHG', 'ITG-DR', 'ITG-SEC'],
}

const RISK_LEVEL_OPTIONS = [
  { value: 'LR', label: 'LR — 낮음' },
  { value: 'MR', label: 'MR — 보통' },
  { value: 'HR', label: 'HR — 높음' },
  { value: 'SR', label: 'SR — 유의' },
]

function FieldError({ name }: { name: string }) {
  const { formState: { errors } } = useFormContext<ControlFormData>()
  const error = errors[name as keyof ControlFormData]
  if (!error || typeof error.message !== 'string') return null
  return <p className="text-xs text-destructive mt-1">{error.message}</p>
}

interface Props {
  isEditMode: boolean
}

export default function BasicInfoTab({ isEditMode }: Props) {
  const { register, control, watch, setValue, formState: { errors } } = useFormContext<ControlFormData>()
  const selectedProcess = watch('process_code')

  const subProcessOptions = selectedProcess ? SUB_PROCESS_MAP[selectedProcess] ?? [] : []

  return (
    <div className="space-y-4 py-2">
      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-1.5">
          <Label htmlFor="code">
            통제 코드 <span className="text-destructive">*</span>
          </Label>
          <Input
            id="code"
            {...register('code')}
            readOnly={isEditMode}
            className={isEditMode ? 'bg-muted cursor-not-allowed' : ''}
            placeholder="예: O2C-AR-C001"
          />
          <FieldError name="code" />
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="owner_name">담당자명</Label>
          <Input id="owner_name" {...register('owner_name')} placeholder="예: 김재무" />
        </div>
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="name">
          통제명 <span className="text-destructive">*</span>
        </Label>
        <Input id="name" {...register('name')} placeholder="통제명을 입력하세요" />
        <FieldError name="name" />
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-1.5">
          <Label>
            프로세스 <span className="text-destructive">*</span>
          </Label>
          <Controller
            name="process_code"
            control={control}
            render={({ field }) => (
              <Select
                value={field.value}
                onValueChange={(v) => {
                  field.onChange(v)
                  setValue('sub_process_code', '')
                }}
              >
                <SelectTrigger>
                  <SelectValue placeholder="프로세스 선택" />
                </SelectTrigger>
                <SelectContent>
                  {PROCESS_CODES.map((c) => (
                    <SelectItem key={c} value={c}>{c}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}
          />
          {errors.process_code && (
            <p className="text-xs text-destructive mt-1">{errors.process_code.message}</p>
          )}
        </div>

        <div className="space-y-1.5">
          <Label>
            세부 프로세스 <span className="text-destructive">*</span>
          </Label>
          <Controller
            name="sub_process_code"
            control={control}
            render={({ field }) => (
              <Select
                value={field.value}
                onValueChange={field.onChange}
                disabled={!selectedProcess}
              >
                <SelectTrigger>
                  <SelectValue placeholder={selectedProcess ? '선택' : '프로세스 먼저 선택'} />
                </SelectTrigger>
                <SelectContent>
                  {subProcessOptions.map((c) => (
                    <SelectItem key={c} value={c}>{c}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}
          />
          {errors.sub_process_code && (
            <p className="text-xs text-destructive mt-1">{errors.sub_process_code.message}</p>
          )}
        </div>
      </div>

      <div className="space-y-1.5">
        <Label>
          위험 수준 <span className="text-destructive">*</span>
        </Label>
        <Controller
          name="risk_level"
          control={control}
          render={({ field }) => (
            <Select value={field.value} onValueChange={field.onChange}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {RISK_LEVEL_OPTIONS.map((o) => (
                  <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}
        />
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="objective">통제 목적</Label>
        <Textarea id="objective" {...register('objective')} rows={2} placeholder="통제 목적을 입력하세요" />
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="description">통제 설명</Label>
        <Textarea id="description" {...register('description')} rows={3} placeholder="통제 절차를 상세히 설명하세요" />
      </div>
    </div>
  )
}
