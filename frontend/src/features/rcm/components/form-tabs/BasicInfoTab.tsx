import { Controller, useFormContext } from 'react-hook-form'
import { useQuery } from '@tanstack/react-query'
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
import { fetchProcesses, fetchSubProcesses, fetchRisksBySubProcessId } from '../../api/controlsApi'
import type { ControlFormData } from '../ControlFormDialog'

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
  const { register, control, watch, setValue } = useFormContext<ControlFormData>()
  const selectedProcessCode = watch('process_code')
  const selectedSubProcessCode = watch('sub_process_code')

  // ── 1. 프로세스 목록 ──────────────────────────────────────
  const { data: processesData, isLoading: processesLoading } = useQuery({
    queryKey: ['processes'],
    queryFn: fetchProcesses,
    staleTime: 1000 * 60 * 10,
    enabled: !isEditMode,
  })

  const selectedProcess = processesData?.items.find((p) => p.code === selectedProcessCode)

  // ── 2. 세부 프로세스 목록 (process_id 서버 필터) ──────────
  const { data: subProcessesData, isLoading: subProcessesLoading } = useQuery({
    queryKey: ['sub-processes', selectedProcess?.id],
    queryFn: () => fetchSubProcesses(selectedProcess!.id),
    enabled: !!selectedProcess?.id && !isEditMode,
    staleTime: 1000 * 60 * 10,
  })

  const selectedSubProcess = subProcessesData?.items.find((sp) => sp.code === selectedSubProcessCode)

  // ── 3. 위험 목록 (sub_process_id 서버 필터) ───────────────
  const { data: risksData, isLoading: risksLoading } = useQuery({
    queryKey: ['risks', selectedSubProcess?.id],
    queryFn: () => fetchRisksBySubProcessId(selectedSubProcess!.id),
    enabled: !!selectedSubProcess?.id && !isEditMode,
    staleTime: 1000 * 60 * 10,
  })

  return (
    <div className="space-y-4 py-2">

      {/* 통제 코드 + 담당자 */}
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

      {/* 통제명 */}
      <div className="space-y-1.5">
        <Label htmlFor="name">
          통제명 <span className="text-destructive">*</span>
        </Label>
        <Input id="name" {...register('name')} placeholder="통제명을 입력하세요" />
        <FieldError name="name" />
      </div>

      {/* 프로세스 + 세부 프로세스 */}
      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-1.5">
          <Label>
            프로세스 <span className="text-destructive">*</span>
          </Label>
          {isEditMode ? (
            <Input value={selectedProcessCode} readOnly className="bg-muted cursor-not-allowed" />
          ) : (
            <Controller
              name="process_code"
              control={control}
              render={({ field }) => (
                <Select
                  value={field.value}
                  onValueChange={(v) => {
                    field.onChange(v)
                    setValue('sub_process_code', '')
                    setValue('risk_id', '')
                  }}
                >
                  <SelectTrigger>
                    <SelectValue placeholder={processesLoading ? '불러오는 중...' : '프로세스 선택'} />
                  </SelectTrigger>
                  <SelectContent>
                    {(processesData?.items ?? []).map((p) => (
                      <SelectItem key={p.id} value={p.code}>
                        {p.code} — {p.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}
            />
          )}
          <FieldError name="process_code" />
        </div>

        <div className="space-y-1.5">
          <Label>
            세부 프로세스 <span className="text-destructive">*</span>
          </Label>
          {isEditMode ? (
            <Input value={selectedSubProcessCode} readOnly className="bg-muted cursor-not-allowed" />
          ) : (
            <Controller
              name="sub_process_code"
              control={control}
              render={({ field }) => (
                <Select
                  value={field.value}
                  onValueChange={(v) => {
                    field.onChange(v)
                    setValue('risk_id', '')
                  }}
                  disabled={!selectedProcess}
                >
                  <SelectTrigger>
                    <SelectValue placeholder={
                      !selectedProcess ? '프로세스를 먼저 선택하세요'
                      : subProcessesLoading ? '불러오는 중...'
                      : '세부 프로세스 선택'
                    } />
                  </SelectTrigger>
                  <SelectContent>
                    {(subProcessesData?.items ?? []).map((sp) => (
                      <SelectItem key={sp.id} value={sp.code}>
                        {sp.code} — {sp.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}
            />
          )}
          <FieldError name="sub_process_code" />
        </div>
      </div>

      {/* 위험 항목 */}
      <div className="space-y-1.5">
        <Label>
          위험 항목 <span className="text-destructive">*</span>
        </Label>
        {isEditMode ? (
          <Input value={watch('risk_level') ?? ''} readOnly className="bg-muted cursor-not-allowed" />
        ) : (
          <Controller
            name="risk_id"
            control={control}
            render={({ field }) => (
              <Select
                value={field.value ?? ''}
                onValueChange={(v) => {
                  field.onChange(v)
                  const risk = risksData?.items.find((r) => r.id === v)
                  if (risk) setValue('risk_level', risk.assessment_level)
                }}
                disabled={!selectedSubProcess}
              >
                <SelectTrigger>
                  <SelectValue placeholder={
                    !selectedSubProcess ? '세부 프로세스를 먼저 선택하세요'
                    : risksLoading ? '불러오는 중...'
                    : '위험 항목 선택'
                  } />
                </SelectTrigger>
                <SelectContent>
                  {(risksData?.items ?? []).map((r) => (
                    <SelectItem key={r.id} value={r.id}>
                      {r.code} — {r.description} ({r.assessment_level})
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}
          />
        )}
      </div>

      {/* 통제 목적 */}
      <div className="space-y-1.5">
        <Label htmlFor="objective">통제 목적</Label>
        <Textarea id="objective" {...register('objective')} rows={2} placeholder="통제 목적을 입력하세요" />
      </div>

      {/* 통제 설명 */}
      <div className="space-y-1.5">
        <Label htmlFor="description">통제 설명</Label>
        <Textarea id="description" {...register('description')} rows={3} placeholder="통제 절차를 상세히 설명하세요" />
      </div>

    </div>
  )
}
