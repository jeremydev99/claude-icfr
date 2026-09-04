import { useEffect } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { toast } from 'sonner'
import { Loader2 } from 'lucide-react'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Button } from '@/components/ui/button'
import type { RiskItem, SubProcessItem } from '../../types'
import { RISK_LEVEL_LABELS } from '../../types'
import { useCreateRisk, useUpdateRisk } from '../../api/useHierarchy'
import { isBaseline } from '../../api/sourceEnvelope'
import { extractHierarchyErrorMessage } from '../../api/errors'

const schema = z.object({
  code: z.string().min(1, '코드는 필수입니다').max(30),
  description: z.string().min(1, '위험 설명은 필수입니다'),
  assessment_level: z.enum(['LR', 'MR', 'HR', 'SR']),
  sub_process_id: z.string().min(1, '상위 세부 프로세스를 선택하세요'),
})

type FormData = z.infer<typeof schema>

interface Props {
  open: boolean
  onOpenChange: (open: boolean) => void
  editTarget: RiskItem | null
  subProcesses: SubProcessItem[]
}

export default function RiskFormDialog({ open, onOpenChange, editTarget, subProcesses }: Props) {
  const isEdit = !!editTarget
  const createMutation = useCreateRisk()
  const updateMutation = useUpdateRisk()
  const isPending = createMutation.isPending || updateMutation.isPending
  const showBaselineHint = isEdit && isBaseline(editTarget?.envelope)

  const form = useForm<FormData>({
    resolver: zodResolver(schema),
    defaultValues: { code: '', description: '', assessment_level: 'MR', sub_process_id: '' },
  })

  useEffect(() => {
    if (!open) return
    if (isEdit && editTarget) {
      form.reset({
        code: editTarget.code,
        description: editTarget.description,
        assessment_level: editTarget.assessment_level,
        sub_process_id: editTarget.sub_process_id,
      })
    } else {
      form.reset({ code: '', description: '', assessment_level: 'MR', sub_process_id: '' })
    }
  }, [open, isEdit, editTarget, form])

  const onSubmit = async (data: FormData) => {
    try {
      if (isEdit && editTarget) {
        await updateMutation.mutateAsync({
          id: editTarget.id,
          payload: { description: data.description, assessment_level: data.assessment_level },
        })
        toast.success('위험이 수정되었습니다')
      } else {
        await createMutation.mutateAsync({
          code: data.code,
          description: data.description,
          assessment_level: data.assessment_level,
          sub_process_id: data.sub_process_id,
        })
        toast.success('위험이 추가되었습니다')
      }
      onOpenChange(false)
    } catch (err) {
      toast.error(extractHierarchyErrorMessage(err))
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>{isEdit ? '위험 편집' : '위험 추가'}</DialogTitle>
          <DialogDescription>
            {isEdit ? '위험 정보를 수정합니다.' : '새 위험을 등록합니다.'} 필수 항목을 모두 입력해 주세요.
          </DialogDescription>
          {showBaselineHint && (
            <p className="text-xs text-amber-600 bg-amber-50 border border-amber-200 rounded px-2.5 py-1.5">
              이 위험은 기준(baseline)입니다 — 저장 시 귀사 재정의(override)로 기록됩니다.
            </p>
          )}
        </DialogHeader>

        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
            <FormField
              control={form.control}
              name="sub_process_id"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>상위 세부 프로세스</FormLabel>
                  <Select value={field.value} onValueChange={field.onChange} disabled={isEdit}>
                    <FormControl>
                      <SelectTrigger>
                        <SelectValue placeholder="세부 프로세스 선택" />
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      {subProcesses.map((sp) => (
                        <SelectItem key={sp.id} value={sp.id}>
                          {sp.code} — {sp.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <FormMessage />
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name="code"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>코드</FormLabel>
                  <FormControl>
                    <Input {...field} disabled={isEdit} placeholder="예: O2C-AR-R001" />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name="description"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>위험 설명</FormLabel>
                  <FormControl>
                    <Textarea {...field} rows={3} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name="assessment_level"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>위험 수준</FormLabel>
                  <Select value={field.value} onValueChange={field.onChange}>
                    <FormControl>
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      {(Object.entries(RISK_LEVEL_LABELS) as [FormData['assessment_level'], string][]).map(
                        ([value, label]) => (
                          <SelectItem key={value} value={value}>
                            {label}
                          </SelectItem>
                        ),
                      )}
                    </SelectContent>
                  </Select>
                  <FormMessage />
                </FormItem>
              )}
            />

            <DialogFooter className="pt-2">
              <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
                취소
              </Button>
              <Button type="submit" disabled={isPending}>
                {isPending && <Loader2 className="h-3.5 w-3.5 mr-1 animate-spin" />}
                {isEdit ? '수정' : '추가'}
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  )
}
