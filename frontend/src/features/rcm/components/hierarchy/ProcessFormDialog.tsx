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
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Button } from '@/components/ui/button'
import type { ProcessItem } from '../../types'
import { useCreateProcess, useUpdateProcess } from '../../api/useHierarchy'
import { isBaseline } from '../../api/sourceEnvelope'
import { extractHierarchyErrorMessage } from '../../api/errors'

const schema = z.object({
  code: z.string().min(1, '코드는 필수입니다').max(20),
  name: z.string().min(1, '프로세스명은 필수입니다').max(100),
  description: z.string().nullable().optional(),
})

type FormData = z.infer<typeof schema>

interface Props {
  open: boolean
  onOpenChange: (open: boolean) => void
  editTarget: ProcessItem | null
}

export default function ProcessFormDialog({ open, onOpenChange, editTarget }: Props) {
  const isEdit = !!editTarget
  const createMutation = useCreateProcess()
  const updateMutation = useUpdateProcess()
  const isPending = createMutation.isPending || updateMutation.isPending
  const showBaselineHint = isEdit && isBaseline(editTarget?.envelope)

  const form = useForm<FormData>({
    resolver: zodResolver(schema),
    defaultValues: { code: '', name: '', description: '' },
  })

  useEffect(() => {
    if (!open) return
    if (isEdit && editTarget) {
      form.reset({ code: editTarget.code, name: editTarget.name, description: editTarget.description ?? '' })
    } else {
      form.reset({ code: '', name: '', description: '' })
    }
  }, [open, isEdit, editTarget, form])

  const onSubmit = async (data: FormData) => {
    try {
      if (isEdit && editTarget) {
        await updateMutation.mutateAsync({
          id: editTarget.id,
          payload: { name: data.name, description: data.description || null },
        })
        toast.success('프로세스가 수정되었습니다')
      } else {
        await createMutation.mutateAsync({
          code: data.code,
          name: data.name,
          description: data.description || null,
        })
        toast.success('프로세스가 추가되었습니다')
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
          <DialogTitle>{isEdit ? '프로세스 편집' : '프로세스 추가'}</DialogTitle>
          <DialogDescription>
            {isEdit ? '프로세스 정보를 수정합니다.' : '새 프로세스를 등록합니다.'} 필수 항목을 모두 입력해 주세요.
          </DialogDescription>
          {showBaselineHint && (
            <p className="text-xs text-amber-600 bg-amber-50 border border-amber-200 rounded px-2.5 py-1.5">
              이 프로세스는 기준(baseline)입니다 — 저장 시 귀사 재정의(override)로 기록됩니다.
            </p>
          )}
        </DialogHeader>

        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
            <FormField
              control={form.control}
              name="code"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>코드</FormLabel>
                  <FormControl>
                    <Input {...field} disabled={isEdit} placeholder="예: O2C" />
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
                  <FormLabel>프로세스명</FormLabel>
                  <FormControl>
                    <Input {...field} placeholder="예: 수익주기" />
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
                  <FormLabel>설명 (선택)</FormLabel>
                  <FormControl>
                    <Textarea {...field} value={field.value ?? ''} rows={3} />
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
