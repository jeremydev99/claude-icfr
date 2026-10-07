import { useState } from 'react'
import { toast } from 'sonner'
import { Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import apiClient from '@/lib/axios'
import { PASSWORD_RULE_TEXT, passwordError } from '../password.pure'
import { useAuthStore } from '../store'

/** 본인 비밀번호 변경 — `POST /api/auth/change-password`(서버가 현재 비밀번호를 확인한다). */
export default function ChangePasswordDialog({ open, onOpenChange, forced = false }: {
  open: boolean
  onOpenChange: (v: boolean) => void
  /** 관리자가 정한 비밀번호로 들어온 경우(ADR-0041) — 닫을 수 없고, 바꾸면 화면이 열린다 */
  forced?: boolean
}) {
  const [current, setCurrent] = useState('')
  const [next, setNext] = useState('')
  const [confirm, setConfirm] = useState('')
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const close = (v: boolean) => {
    if (!v && forced) return
    if (!v) {
      setCurrent(''); setNext(''); setConfirm(''); setError(null)
    }
    onOpenChange(v)
  }

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    const problem = passwordError(current, next, confirm)
    if (problem) return setError(problem)
    setPending(true)
    try {
      const { data } = await apiClient.post<{ access_token: string; refresh_token: string }>(
        '/api/auth/change-password', { old_password: current, new_password: next })
      // 변경 전 토큰은 서버가 무효로 본다(다른 기기 세션 종료) — 이 기기는 새 토큰으로 이어간다
      const store = useAuthStore.getState()
      store.setTokens(data.access_token, data.refresh_token)
      toast.success('비밀번호를 바꿨습니다 — 다른 기기의 로그인은 끊깁니다')
      if (store.user?.must_change_password) store.setUser({ ...store.user, must_change_password: false })
      setCurrent(''); setNext(''); setConfirm(''); setError(null)
      onOpenChange(false)
    } catch (err) {
      const detail = (err as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
      setError(typeof detail === 'string' ? detail : '비밀번호를 바꾸지 못했습니다')
    } finally {
      setPending(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={close}>
      <DialogContent className={forced ? 'max-w-sm [&>button:last-child]:hidden' : 'max-w-sm'}
        onEscapeKeyDown={(e) => forced && e.preventDefault()} onPointerDownOutside={(e) => forced && e.preventDefault()}>
        <DialogHeader>
          <DialogTitle>{forced ? '비밀번호를 먼저 바꿔 주세요' : '비밀번호 변경'}</DialogTitle>
          <DialogDescription>
            {forced && '관리자가 정한 임시 비밀번호입니다 — 본인만 아는 비밀번호로 바꿔야 시작할 수 있습니다. '}
            새 비밀번호: {PASSWORD_RULE_TEXT}. 바꾸면 다른 기기의 로그인은 끊깁니다.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={submit} className="space-y-3 text-sm">
          <label className="block space-y-1">
            <span>현재 비밀번호</span>
            <Input type="password" autoComplete="current-password" value={current}
              onChange={(e) => { setCurrent(e.target.value); setError(null) }} autoFocus />
          </label>
          <label className="block space-y-1">
            <span>새 비밀번호</span>
            <Input type="password" autoComplete="new-password" value={next}
              onChange={(e) => { setNext(e.target.value); setError(null) }} />
          </label>
          <label className="block space-y-1">
            <span>새 비밀번호 확인</span>
            <Input type="password" autoComplete="new-password" value={confirm}
              onChange={(e) => { setConfirm(e.target.value); setError(null) }} />
          </label>
          {error && <p className="text-sm text-red-600" role="alert">{error}</p>}
          <DialogFooter>
            {!forced && <Button type="button" variant="ghost" onClick={() => close(false)}>취소</Button>}
            <Button type="submit" disabled={pending}>
              {pending && <Loader2 className="mr-1 h-4 w-4 animate-spin" />}변경
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
