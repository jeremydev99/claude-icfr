import { useEffect } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { toast } from 'sonner'
import { isAxiosError } from 'axios'
import {
  Dialog,
  DialogContent,
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
import { Loader2 } from 'lucide-react'
import { useUsers } from '../api/useUsers'
import { useCreateUserRole, useUpdateUserRole } from '../api/useUserRoles'
import type { UserRole } from '../types'
import { ROLE_NAME_OPTIONS } from '../types'

const schema = z.object({
  user_id: z.string().min(1, '사용자를 선택하세요'),
  role_name: z.string().min(1, '역할을 선택하세요'),
  scope: z.string().optional(),
})

type FormData = z.infer<typeof schema>

interface Props {
  open: boolean
  onOpenChange: (open: boolean) => void
  editTarget: UserRole | null
}

function extractErrorMessage(err: unknown): string {
  if (isAxiosError(err)) {
    const data = err.response?.data
    if (typeof data?.detail === 'string') return data.detail
    if (Array.isArray(data?.detail)) return data.detail.map((d: { msg: string }) => d.msg).join(', ')
    if (err.response?.status === 401) return '로그인이 필요합니다'
    if (err.response?.status === 422) return '입력값을 확인해주세요'
  }
  return '알 수 없는 오류가 발생했습니다'
}

export default function UserRoleFormDialog({ open, onOpenChange, editTarget }: Props) {
  const isEdit = !!editTarget
  const { data: usersData } = useUsers({ skip: 0, limit: 200 })
  const createMutation = useCreateUserRole()
  const updateMutation = useUpdateUserRole()
  const isPending = createMutation.isPending || updateMutation.isPending

  const form = useForm<FormData>({
    resolver: zodResolver(schema),
    defaultValues: { user_id: '', role_name: '', scope: '' },
  })

  useEffect(() => {
    if (!open) return
    if (isEdit && editTarget) {
      form.reset({
        user_id: editTarget.user_id,
        role_name: editTarget.role_name,
        scope: editTarget.scope ?? '',
      })
    } else {
      form.reset({ user_id: '', role_name: '', scope: '' })
    }
  }, [open, isEdit, editTarget, form])

  const onSubmit = async (data: FormData) => {
    try {
      if (isEdit) {
        await updateMutation.mutateAsync({
          id: editTarget!.id,
          payload: {
            role_name: data.role_name,
            scope: data.scope || null,
          },
        })
        toast.success('역할이 수정되었습니다')
      } else {
        await createMutation.mutateAsync({
          user_id: data.user_id,
          role_name: data.role_name,
          scope: data.scope || null,
        })
        toast.success('역할이 등록되었습니다')
      }
      onOpenChange(false)
    } catch (err) {
      toast.error(extractErrorMessage(err))
    }
  }

  const users = usersData?.items ?? []

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>{isEdit ? '역할 편집' : '역할 등록'}</DialogTitle>
        </DialogHeader>

        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
            {/* 사용자 선택 — 편집 시 잠금 */}
            <FormField
              control={form.control}
              name="user_id"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>사용자</FormLabel>
                  <Select
                    value={field.value}
                    onValueChange={field.onChange}
                    disabled={isEdit}
                  >
                    <FormControl>
                      <SelectTrigger>
                        <SelectValue placeholder="사용자 선택" />
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      {users.map((u) => (
                        <SelectItem key={u.id} value={u.id}>
                          {u.display_name} ({u.email})
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <FormMessage />
                </FormItem>
              )}
            />

            {/* 역할명 선택 */}
            <FormField
              control={form.control}
              name="role_name"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>역할</FormLabel>
                  <Select value={field.value} onValueChange={field.onChange}>
                    <FormControl>
                      <SelectTrigger>
                        <SelectValue placeholder="역할 선택" />
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      {ROLE_NAME_OPTIONS.map((o) => (
                        <SelectItem key={o.value} value={o.value}>
                          {o.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <FormMessage />
                </FormItem>
              )}
            />

            {/* 범위 (선택) */}
            <FormField
              control={form.control}
              name="scope"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>범위 (선택)</FormLabel>
                  <FormControl>
                    <Input placeholder="예: O2C, P2P, 전사" {...field} />
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
                {isEdit ? '수정' : '등록'}
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  )
}
