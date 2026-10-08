import { MailCheck, MailWarning } from 'lucide-react'

/**
 * 링크 메일 발송 결과(2026-10-08) — 사내 메일서버로 보낸다. 설정이 없거나(null) 실패해도 링크는 그대로 보여 주므로
 * 관리자가 직접 전달하면 된다.
 */
export default function MailNotice({ sent, error, to }: {
  sent?: boolean | null
  error?: string | null
  to?: string
}) {
  if (sent == null) return null
  if (sent) {
    return (
      <p className="flex items-center gap-1.5 rounded-md bg-emerald-500/10 px-3 py-2 text-sm text-emerald-700 dark:text-emerald-400">
        <MailCheck className="h-4 w-4 shrink-0" />
        {to ? `${to} 로 메일을 보냈습니다.` : '메일을 보냈습니다.'} 받지 못했다면 아래 링크를 직접 전달하세요.
      </p>
    )
  }
  return (
    <p className="flex items-center gap-1.5 rounded-md bg-amber-500/10 px-3 py-2 text-sm text-amber-700 dark:text-amber-400">
      <MailWarning className="h-4 w-4 shrink-0" />
      메일을 보내지 못했습니다{error ? ` (${error})` : ''}. 아래 링크를 직접 전달하세요.
    </p>
  )
}
