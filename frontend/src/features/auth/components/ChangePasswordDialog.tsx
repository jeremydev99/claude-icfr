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
export default function ChangePasswordDialog({ open, onOpenChange }: {
  open: boolean
  onOpenChange: (v: boolean) => void
}) {
  const [current, setCurrent] = useState('')
  const [next, setNext] = useState('')
  const [confirm, setConfirm] = useState('')
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const close = (v: boolean) => {
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
      useAuthStore.getState().setTokens(data.access_token, data.refresh_token)
      toast.success('비밀번호를 바꿨습니다 — 다른 기기의 로그인은 끊깁니다')
      close(false)
    } catch (err) {
      const detail = (err as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
      setError(typeof detail === 'string' ? detail : '비밀번호를 바꾸지 못했습니다')
    } finally {
      setPending(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={close}>
      <DialogContent className="max-w-sm">
        <DialogHeader>
          <DialogTitle>비밀번호 변경</DialogTitle>
          <DialogDescription>새 비밀번호: {PASSWORD_RULE_TEXT}. 바꾸면 다른 기기의 로그인은 끊깁니다.</DialogDescription>
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
            <Button type="button" variant="ghost" onClick={() => close(false)}>취소</Button>
            <Button type="submit" disabled={pending}>
              {pending && <Loader2 className="mr-1 h-4 w-4 animate-spin" />}변경
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
