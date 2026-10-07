import { useEffect, useState } from 'react'
import { PASSWORD_RULE_TEXT, passwordPolicyError } from '@/features/auth/password.pure'
import {
  Dialog,
  DialogContent,
  DialogDescription,
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
import type { User, UserCreated } from '../types'
import SetupLinkView from './SetupLinkView'

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
  // 기본은 초대(설정 링크). 비상용으로만 관리자가 비밀번호를 정한다 — 다음 로그인 때 본인이 바꿔야 한다(ADR-0041)
  const [emergency, setEmergency] = useState(false)
  const [created, setCreated] = useState<UserCreated | null>(null)

  useEffect(() => {
    if (open) {
      setEmail(editTarget?.email ?? '')
      setPassword('')
      setDisplayName(editTarget?.display_name ?? '')
      setRole(editTarget?.role ?? 'user')
      setIsActive(editTarget?.is_active ?? true)
      setError(null)
      setEmergency(false)
      setCreated(null)
    }
  }, [open, editTarget])

  const isPending = createUser.isPending || updateUser.isPending

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)

    const policy = isEdit || !emergency ? null : passwordPolicyError(password)
    if (policy) {
      setError(policy)
      return
    }

    try {
      if (isEdit) {
        await updateUser.mutateAsync({
          id: editTarget.id,
          body: { display_name: displayName, role, is_active: isActive },
        })
      } else {
        const u = await createUser.mutateAsync({
          email, display_name: displayName, role, ...(emergency ? { password } : {}),
        })
        onSuccess?.()
        if (u.setup_url) {
          setCreated(u)   // 링크를 보여 주고 창은 관리자가 닫는다
          return
        }
        onOpenChange(false)
        return
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
          <DialogDescription>
            {isEdit ? '사용자 정보를 수정합니다. 필수 항목을 모두 입력해 주세요.'
              : '이메일·이름·역할만 입력하면 계정 시작 링크가 만들어집니다. 비밀번호는 직원 본인이 정하고, 관리자는 알 수 없습니다.'}
          </DialogDescription>
        </DialogHeader>
        {created?.setup_url ? (
          <div className="space-y-4">
            <SetupLinkView url={created.setup_url} expiresAt={created.setup_expires_at ?? ''} purpose="invite"
              name={created.display_name} />
            <DialogFooter><Button onClick={() => onOpenChange(false)}>닫기</Button></DialogFooter>
          </div>
        ) : (
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
              {emergency && (
                <div className="space-y-1.5 rounded-lg border border-amber-300 bg-amber-50/60 p-3 dark:bg-amber-950/20">
                  <Label htmlFor="password">비상용 비밀번호 * ({PASSWORD_RULE_TEXT})</Label>
                  <Input
                    id="password"
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                    placeholder="••••••••"
                  />
                  <p className="text-xs text-amber-800 dark:text-amber-300">
                    링크를 전달할 수 없을 때만 쓰세요. 직원은 처음 로그인하면 본인 비밀번호로 바꿔야 다른 기능을 쓸 수 있습니다.
                  </p>
                </div>
              )}
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
          <DialogFooter className="sm:items-center">
            {!isEdit && (
              <button type="button" onClick={() => setEmergency(!emergency)}
                className="mr-auto text-xs text-muted-foreground underline-offset-2 hover:underline">
                {emergency ? '링크로 시작하기(권장)' : '비상용: 비밀번호 직접 정하기'}
              </button>
            )}
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              취소
            </Button>
            <Button type="submit" disabled={isPending}>
              {isPending && <Loader2 className="h-3.5 w-3.5 mr-1 animate-spin" />}
              {isEdit ? '저장' : emergency ? '등록' : '등록하고 링크 만들기'}
            </Button>
          </DialogFooter>
        </form>
        )}
      </DialogContent>
    </Dialog>
  )
}
