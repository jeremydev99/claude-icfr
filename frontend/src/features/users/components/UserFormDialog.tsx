import { useEffect, useState } from 'react'
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Loader2 } from 'lucide-react'
import { useCreateUser, useUpdateUser } from '../api/useUsers'
import type { User } from '../types'

interface Props {
  open: boolean
  onOpenChange: (open: boolean) => void
  editTarget: User | null
  onSuccess?: () => void
}

const USER_ROLE_OPTIONS = [
  { value: 'user', label: '일반 사용자' },
  { value: 'admin', label: '관리자' },
]

const getErrorDetail = (e: unknown) =>
  (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail

export default function UserFormDialog({ open, onOpenChange, editTarget, onSuccess }: Props) {
  const isEdit = !!editTarget
  const createUser = useCreateUser()
  const updateUser = useUpdateUser()

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [role, setRole] = useState('user')
  const [isActive, setIsActive] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (open) {
      setEmail(editTarget?.email ?? '')
      setPassword('')
      setDisplayName(editTarget?.display_name ?? '')
      setRole(editTarget?.role ?? 'user')
      setIsActive(editTarget?.is_active ?? true)
      setError(null)
    }
  }, [open, editTarget])

  const isPending = createUser.isPending || updateUser.isPending

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)

    if (!isEdit && password.length < 8) {
      setError('비밀번호는 8자 이상이어야 합니다')
      return
    }

    try {
      if (isEdit) {
        await updateUser.mutateAsync({
          id: editTarget.id,
          body: { display_name: displayName, role, is_active: isActive },
        })
      } else {
        await createUser.mutateAsync({ email, password, display_name: displayName, role })
      }
      onOpenChange(false)
      onSuccess?.()
    } catch (err) {
      setError(getErrorDetail(err) ?? '저장에 실패했습니다')
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>{isEdit ? '사용자 편집' : '사용자 등록'}</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4 py-2">
          {!isEdit && (
            <>
              <div className="space-y-1.5">
                <Label htmlFor="email">이메일 *</Label>
                <Input
                  id="email"
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  placeholder="user@example.com"
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="password">비밀번호 * (8자 이상)</Label>
                <Input
                  id="password"
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  placeholder="••••••••"
                />
              </div>
            </>
          )}
          {isEdit && (
            <div className="space-y-1.5">
              <Label>이메일</Label>
              <Input value={editTarget.email} disabled className="bg-muted" />
            </div>
          )}
          <div className="space-y-1.5">
            <Label htmlFor="display_name">이름 (실명) *</Label>
            <Input
              id="display_name"
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              required
              placeholder="홍길동"
            />
          </div>
          <div className="space-y-1.5">
            <Label>역할</Label>
            <Select value={role} onValueChange={setRole}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {USER_ROLE_OPTIONS.map((o) => (
                  <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          {isEdit && (
            <div className="flex items-center gap-3">
              <input
                id="is_active"
                type="checkbox"
                checked={isActive}
                onChange={(e) => setIsActive(e.target.checked)}
                className="h-4 w-4 rounded border-gray-300"
              />
              <Label htmlFor="is_active">활성 계정</Label>
            </div>
          )}
          {error && <p className="text-sm text-destructive">{error}</p>}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              취소
            </Button>
            <Button type="submit" disabled={isPending}>
              {isPending && <Loader2 className="h-3.5 w-3.5 mr-1 animate-spin" />}
              {isEdit ? '저장' : '등록'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
