import { useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { ShieldCheck } from 'lucide-react'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { useAuthStore } from '../store'
import MfaEnroll from './MfaEnroll'

/**
 * 사이드바의 2단계 인증 — 미등록이면 등록, 등록돼 있으면 상태 안내.
 * 휴대폰 교체 등으로 다시 등록하려면 관리자 초기화(사용자 관리) 후 로그인 때 다시 등록한다 —
 * 본인이 직접 끄는 기능은 두지 않는다(탈취된 세션이 MFA 를 끌 수 없게).
 */
export default function MfaDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (o: boolean) => void }) {
  const user = useAuthStore((s) => s.user)
  const qc = useQueryClient()
  const [key, setKey] = useState(0)
  const enabled = Boolean(user?.mfa_enabled)

  return (
    <Dialog open={open} onOpenChange={(o) => { onOpenChange(o); if (!o) setKey((k) => k + 1) }}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2"><ShieldCheck className="h-5 w-5 text-primary" />2단계 인증</DialogTitle>
          <DialogDescription>
            {enabled
              ? '이 계정은 2단계 인증을 사용 중입니다. 로그인할 때마다 인증 앱의 6자리를 입력합니다.'
              : user?.mfa_required
                ? '이 계정은 2단계 인증이 필요합니다. 지금 등록하세요.'
                : '비밀번호가 유출돼도 계정을 지킬 수 있습니다. 마스터·책임관리자는 2026-11-02 부터 의무입니다.'}
          </DialogDescription>
        </DialogHeader>
        {enabled ? (
          <div className="space-y-3 text-sm text-muted-foreground">
            <p>휴대폰을 바꾸거나 잃어버렸다면 보관한 복구 코드로 로그인한 뒤, 시스템관리자에게 2단계 인증 초기화를 요청하세요.
              초기화 후 다음 로그인 때 새 휴대폰으로 다시 등록합니다.</p>
            <Button variant="outline" className="w-full" onClick={() => onOpenChange(false)}>닫기</Button>
          </div>
        ) : (
          open && (
            <MfaEnroll key={key} onDone={() => {
              void qc.invalidateQueries({ queryKey: ['me'] })
              onOpenChange(false)
            }} />
          )
        )}
      </DialogContent>
    </Dialog>
  )
}
