import { useState, useEffect } from 'react'
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
import { Link2, Loader2 } from 'lucide-react'
import { useIssueSetupLink, useResetPassword } from '../api/useUsers'
import type { SetupLink, User } from '../types'
import SetupLinkView from './SetupLinkView'

interface Props {
  open: boolean
  onOpenChange: (open: boolean) => void
  targetUser: User | null
  onSuccess?: () => void
}

const getErrorDetail = (e: unknown) =>
  (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail

/**
 * 비밀번호 재설정(ADR-0041) — 기본은 설정 링크 발급(관리자는 비밀번호를 모른다).
 * 링크를 전달할 수 없을 때만 비상용으로 직접 정하고, 그 직원은 다음 로그인 때 바꿔야 한다.
 */
export default function ResetPasswordDialog({ open, onOpenChange, targetUser, onSuccess }: Props) {
  const resetPwd = useResetPassword()
  const issue = useIssueSetupLink()
  const [link, setLink] = useState<SetupLink | null>(null)
  const [emergency, setEmergency] = useState(false)
  const [newPassword, setNewPassword] = useState('')
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (open) {
      setNewPassword('')
      setError(null)
      setLink(null)
      setEmergency(false)
    }
  }, [open])

  const issueLink = async () => {
    if (!targetUser) return
    setError(null)
    try {
      setLink(await issue.mutateAsync(targetUser.id))
    } catch (err) {
      setError(getErrorDetail(err) ?? '링크를 발급하지 못했습니다')
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    const policy = passwordPolicyError(newPassword)
    if (policy) {
      setError(policy)
      return
    }
    if (!targetUser) return
    try {
      await resetPwd.mutateAsync({ id: targetUser.id, body: { new_password: newPassword } })
      onOpenChange(false)
      onSuccess?.()
    } catch (err) {
      setError(getErrorDetail(err) ?? '비밀번호 재설정에 실패했습니다')
    }
  }

  const pending = !!targetUser?.invite_pending
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>{pending ? '계정 시작 링크' : '비밀번호 재설정'}</DialogTitle>
          <DialogDescription>
            {pending
              ? '아직 비밀번호를 정하지 않은 직원입니다. 새 링크를 발급하면 이전 링크는 취소됩니다.'
              : '재설정 링크를 발급해 전달하세요. 직원이 링크에서 새 비밀번호를 정하며, 관리자는 알 수 없습니다.'}
          </DialogDescription>
        </DialogHeader>
        {targetUser && (
          <p className="-mt-1 text-sm text-muted-foreground">
            {targetUser.display_name} ({targetUser.email})
          </p>
        )}
        {link && targetUser ? (
          <>
            <SetupLinkView url={link.setup_url} expiresAt={link.expires_at} purpose={link.purpose} name={targetUser.display_name} />
            <DialogFooter><Button onClick={() => onOpenChange(false)}>닫기</Button></DialogFooter>
          </>
        ) : emergency ? (
          <form onSubmit={handleSubmit} className="space-y-4 py-2">
            <div className="space-y-1.5 rounded-lg border border-amber-300 bg-amber-50/60 p-3 dark:bg-amber-950/20">
              <Label htmlFor="new_password">비상용 비밀번호 ({PASSWORD_RULE_TEXT})</Label>
              <Input id="new_password" type="password" value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)} required placeholder="••••••••" />
              <p className="text-xs text-amber-800 dark:text-amber-300">
                링크를 전달할 수 없을 때만 쓰세요. 기존 로그인은 끊기고, 직원은 다음 로그인 때 본인 비밀번호로 바꿔야 합니다.
              </p>
            </div>
            {error && <p className="text-sm text-destructive">{error}</p>}
            <DialogFooter className="sm:items-center">
              <button type="button" onClick={() => setEmergency(false)}
                className="mr-auto text-xs text-muted-foreground underline-offset-2 hover:underline">링크로 재설정(권장)</button>
              <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>취소</Button>
              <Button type="submit" disabled={resetPwd.isPending}>
                {resetPwd.isPending && <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" />}
                비상용으로 지정
              </Button>
            </DialogFooter>
          </form>
        ) : (
          <>
            {error && <p className="text-sm text-destructive">{error}</p>}
            <DialogFooter className="sm:items-center">
              {!pending && (
                <button type="button" onClick={() => setEmergency(true)}
                  className="mr-auto text-xs text-muted-foreground underline-offset-2 hover:underline">비상용: 직접 정하기</button>
              )}
              <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>취소</Button>
              <Button onClick={issueLink} disabled={issue.isPending}>
                {issue.isPending ? <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" /> : <Link2 className="mr-1 h-3.5 w-3.5" />}
                {pending ? '새 링크 발급' : '재설정 링크 발급'}
              </Button>
            </DialogFooter>
          </>
        )}
      </DialogContent>
    </Dialog>
  )
}
