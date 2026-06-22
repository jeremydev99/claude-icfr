import { useEffect } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { isAxiosError } from 'axios'
import { toast } from 'sonner'
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
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
import { useCreateDeficiency, useUpdateDeficiency } from '../api/useDeficiencies'
import type { Deficiency } from '../types'

const schema = z.object({
  code: z.string().min(1).max(20),
  severity: z.enum(['low', 'medium', 'high']),
  description: z.string().min(1),
  status: z.enum(['open', 'in_progress', 'closed']).default('open'),
  fiscal_year: z.number().int().min(2000).max(2100).default(new Date().getFullYear()),
  control_id: z.string().nullable().optional(),
})

type FormValues = z.infer<typeof schema>

interface Props {
  open: boolean
  onOpenChange: (open: boolean) => void
  editTarget?: Deficiency | null
}

function extractErrorMessage(err: unknown): string {
  if (isAxiosError(err)) {
    const data = err.response?.data
    const status = err.response?.status
    if (status === 422) {
      if (Array.isArray(data?.detail)) {
        return data.detail.map((d: { msg: string }) => d.msg).join(', ')
      }
      return '입력값을 확인해주세요'
    }
    if (typeof data?.detail === 'string') return data.detail
    if (!err.response) return '서버에 연결할 수 없습니다'
  }
  return '알 수 없는 오류가 발생했습니다'
}

export default function DeficiencyFormDialog({ open, onOpenChange, editTarget }: Props) {
  const isEdit = !!editTarget

  const {
    register,
    handleSubmit,
    setValue,
    watch,
    reset,
    formState: { errors },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      code: '',
      severity: 'medium',
      description: '',
      status: 'open',
      fiscal_year: new Date().getFullYear(),
      control_id: null,
    },
  })

  useEffect(() => {
    if (open && editTarget) {
      reset({
        code: editTarget.code,
        severity: editTarget.severity,
        description: editTarget.description,
        status: editTarget.status,
        fiscal_year: editTarget.fiscal_year,
        control_id: editTarget.control_id ?? null,
      })
    } else if (open && !editTarget) {
      reset({
        code: '',
        severity: 'medium',
        description: '',
        status: 'open',
        fiscal_year: new Date().getFullYear(),
        control_id: null,
      })
    }
  }, [open, editTarget, reset])

  const createMutation = useCreateDeficiency()
  const updateMutation = useUpdateDeficiency()
  const isPending = createMutation.isPending || updateMutation.isPending

  const onSubmit = async (values: FormValues) => {
    try {
      if (isEdit && editTarget) {
        await updateMutation.mutateAsync({ id: editTarget.id, payload: values })
        toast.success('미비점이 수정되었습니다')
      } else {
        await createMutation.mutateAsync(values)
        toast.success('미비점이 등록되었습니다')
      }
      onOpenChange(false)
    } catch (err) {
      toast.error(extractErrorMessage(err))
    }
  }

  const severity = watch('severity')
  const status = watch('status')

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>{isEdit ? '미비점 편집' : '미비점 등록'}</DialogTitle>
        </DialogHeader>

        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4 py-2">
          <div className="space-y-1.5">
            <Label htmlFor="code">
              코드 <span className="text-destructive">*</span>
            </Label>
            <Input id="code" placeholder="예: DEF-001" {...register('code')} />
            {errors.code && <p className="text-xs text-destructive">{errors.code.message}</p>}
          </div>

          <div className="space-y-1.5">
            <Label>
              심각도 <span className="text-destructive">*</span>
            </Label>
            <Select value={severity} onValueChange={(v) => setValue('severity', v as 'low' | 'medium' | 'high')}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="low">낮음</SelectItem>
                <SelectItem value="medium">중간</SelectItem>
                <SelectItem value="high">높음</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="description">
              설명 <span className="text-destructive">*</span>
            </Label>
            <Textarea id="description" rows={3} placeholder="미비점 내용을 입력하세요" {...register('description')} />
            {errors.description && <p className="text-xs text-destructive">{errors.description.message}</p>}
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <Label>상태</Label>
              <Select value={status} onValueChange={(v) => setValue('status', v as 'open' | 'in_progress' | 'closed')}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="open">미해결</SelectItem>
                  <SelectItem value="in_progress">처리중</SelectItem>
                  <SelectItem value="closed">종결</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="fiscal_year">회계연도</Label>
              <Input
                id="fiscal_year"
                type="number"
                min={2000}
                max={2100}
                {...register('fiscal_year', { valueAsNumber: true })}
              />
            </div>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="control_id">통제 ID (선택)</Label>
            <Input
              id="control_id"
              placeholder="UUID"
              {...register('control_id')}
              onChange={(e) => setValue('control_id', e.target.value || null)}
            />
          </div>

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              취소
            </Button>
            <Button type="submit" disabled={isPending}>
              {isPending ? '저장 중...' : isEdit ? '수정' : '등록'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
