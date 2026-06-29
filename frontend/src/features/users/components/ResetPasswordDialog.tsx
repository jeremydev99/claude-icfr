import { useState, useEffect } from 'react'
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
import { Loader2 } from 'lucide-react'
import { useResetPassword } from '../api/useUsers'
import type { User } from '../types'

interface Props {
  open: boolean
  onOpenChange: (open: boolean) => void
  targetUser: User | null
  onSuccess?: () => void
}

const getErrorDetail = (e: unknown) =>
  (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail

export default function ResetPasswordDialog({ open, onOpenChange, targetUser, onSuccess }: Props) {
  const resetPwd = useResetPassword()
  const [newPassword, setNewPassword] = useState('')
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (open) {
      setNewPassword('')
      setError(null)
    }
  }, [open])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    if (newPassword.length < 8) {
      setError('비밀번호는 8자 이상이어야 합니다')
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

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-sm">
        <DialogHeader>
          <DialogTitle>비밀번호 재설정</DialogTitle>
        </DialogHeader>
        {targetUser && (
          <p className="text-sm text-muted-foreground -mt-1">
            {targetUser.display_name} ({targetUser.email})
          </p>
        )}
        <form onSubmit={handleSubmit} className="space-y-4 py-2">
          <div className="space-y-1.5">
            <Label htmlFor="new_password">새 비밀번호 (8자 이상)</Label>
            <Input
              id="new_password"
              type="password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              required
              placeholder="••••••••"
            />
          </div>
          {error && <p className="text-sm text-destructive">{error}</p>}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              취소
            </Button>
            <Button type="submit" disabled={resetPwd.isPending}>
              {resetPwd.isPending && <Loader2 className="h-3.5 w-3.5 mr-1 animate-spin" />}
              재설정
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
