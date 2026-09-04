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
import { Button } from '@/components/ui/button'
import type { ProcessItem, SubProcessItem } from '../../types'
import { useCreateSubProcess, useUpdateSubProcess } from '../../api/useHierarchy'
import { isBaseline } from '../../api/sourceEnvelope'
import { extractHierarchyErrorMessage } from '../../api/errors'

const schema = z.object({
  code: z.string().min(1, '코드는 필수입니다').max(20),
  name: z.string().min(1, '세부 프로세스명은 필수입니다').max(200),
  process_id: z.string().min(1, '상위 프로세스를 선택하세요'),
})

type FormData = z.infer<typeof schema>

interface Props {
  open: boolean
  onOpenChange: (open: boolean) => void
  editTarget: SubProcessItem | null
  processes: ProcessItem[]
}

export default function SubProcessFormDialog({ open, onOpenChange, editTarget, processes }: Props) {
  const isEdit = !!editTarget
  const createMutation = useCreateSubProcess()
  const updateMutation = useUpdateSubProcess()
  const isPending = createMutation.isPending || updateMutation.isPending
  const showBaselineHint = isEdit && isBaseline(editTarget?.envelope)

  const form = useForm<FormData>({
    resolver: zodResolver(schema),
    defaultValues: { code: '', name: '', process_id: '' },
  })

  useEffect(() => {
    if (!open) return
    if (isEdit && editTarget) {
      form.reset({ code: editTarget.code, name: editTarget.name, process_id: editTarget.process_id })
    } else {
      form.reset({ code: '', name: '', process_id: '' })
    }
  }, [open, isEdit, editTarget, form])

  const onSubmit = async (data: FormData) => {
    try {
      if (isEdit && editTarget) {
        await updateMutation.mutateAsync({ id: editTarget.id, payload: { name: data.name } })
        toast.success('세부 프로세스가 수정되었습니다')
      } else {
        await createMutation.mutateAsync({
          code: data.code,
          name: data.name,
          process_id: data.process_id,
        })
        toast.success('세부 프로세스가 추가되었습니다')
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
          <DialogTitle>{isEdit ? '세부 프로세스 편집' : '세부 프로세스 추가'}</DialogTitle>
          <DialogDescription>
            {isEdit ? '세부 프로세스 정보를 수정합니다.' : '새 세부 프로세스를 등록합니다.'} 필수 항목을 모두 입력해 주세요.
          </DialogDescription>
          {showBaselineHint && (
            <p className="text-xs text-amber-600 bg-amber-50 border border-amber-200 rounded px-2.5 py-1.5">
              이 세부 프로세스는 기준(baseline)입니다 — 저장 시 귀사 재정의(override)로 기록됩니다.
            </p>
          )}
        </DialogHeader>

        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
            <FormField
              control={form.control}
              name="process_id"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>상위 프로세스</FormLabel>
                  <Select value={field.value} onValueChange={field.onChange} disabled={isEdit}>
                    <FormControl>
                      <SelectTrigger>
                        <SelectValue placeholder="프로세스 선택" />
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      {processes.map((p) => (
                        <SelectItem key={p.id} value={p.id}>
                          {p.code} — {p.name}
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
                    <Input {...field} disabled={isEdit} placeholder="예: O2C-AR" />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name="name"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>세부 프로세스명</FormLabel>
                  <FormControl>
                    <Input {...field} placeholder="예: 매출채권" />
                  </FormControl>
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
