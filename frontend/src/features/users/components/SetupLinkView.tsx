import { useState } from 'react'
import { Check, Copy, Link2 } from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import MailNotice from './MailNotice'

/**
 * 설정 링크 표시(ADR-0041) — 원문은 발급 응답에서 한 번만 온다. 관리자는 링크만 전달하고 비밀번호는 직원이 정한다.
 * 메일 설정이 있으면 서버가 메일로도 보낸다(결과는 MailNotice). 실패·미설정이면 직접 전달한다.
 */
export default function SetupLinkView({ url, expiresAt, purpose, name, email, mailSent, mailError }: {
  url: string
  expiresAt: string
  purpose: 'invite' | 'reset'
  name: string
  email?: string
  mailSent?: boolean | null
  mailError?: string | null
}) {
  const [copied, setCopied] = useState(false)
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(url)
      setCopied(true)
      toast.success('링크를 복사했습니다')
    } catch {
      toast.error('복사하지 못했습니다 — 링크를 직접 선택해 복사하세요')
    }
  }
  return (
    <div className="space-y-3 rounded-lg border border-primary/30 bg-primary/5 p-3 text-sm">
      <p className="flex items-center gap-1.5 font-medium">
        <Link2 className="h-4 w-4" />{purpose === 'invite' ? `${name}님 계정 시작 링크` : `${name}님 비밀번호 재설정 링크`}
      </p>
      <MailNotice sent={mailSent} error={mailError} to={email} />
      <div className="flex gap-2">
        <Input readOnly value={url} onFocus={(e) => e.currentTarget.select()} className="font-mono text-xs" />
        <Button type="button" size="sm" onClick={copy} className="shrink-0">
          {copied ? <Check className="mr-1 h-3.5 w-3.5" /> : <Copy className="mr-1 h-3.5 w-3.5" />}복사
        </Button>
      </div>
      <ul className="list-disc space-y-0.5 pl-4 text-xs text-muted-foreground">
        <li>본인에게만 전달하세요(사내 메신저 등). 링크를 연 사람이 비밀번호를 정합니다.</li>
        <li>{new Date(expiresAt).toLocaleString('ko-KR')}까지(72시간) 한 번만 쓸 수 있습니다.</li>
        <li>이 창을 닫으면 링크를 다시 볼 수 없습니다 — 필요하면 새로 발급하세요(이전 링크는 취소).</li>
        {purpose === 'reset' && <li>직원이 새 비밀번호를 정하기 전까지 기존 비밀번호는 그대로 쓸 수 있습니다.</li>}
      </ul>
    </div>
  )
}
