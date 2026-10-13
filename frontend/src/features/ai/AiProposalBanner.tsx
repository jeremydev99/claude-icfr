import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { Sparkles } from 'lucide-react'
import { toast } from 'sonner'
import apiClient from '@/lib/axios'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import type { AiProposal } from './types'

const errDetail = (e: unknown, fb: string) =>
  (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? fb

/**
 * AI 제안 안내(ADR-0042) — 무엇을 보고 언제 제안했는지 보여 주고, 담당자가 검토해 채택하거나 폐기한다.
 * 채택하기 전에 내용을 고칠 수 있고, 채택한 사람이 그 문서의 작성 책임자가 된다. 채택 뒤 승인은 기존 결재선 그대로.
 */
export default function AiProposalBanner({ proposal, canDecide, onDone }: {
  proposal: AiProposal
  canDecide: boolean
  onDone: () => void
}) {
  const [mode, setMode] = useState<'adopt' | 'discard' | null>(null)
  const [text, setText] = useState('')
  const [showBasis, setShowBasis] = useState(false)
  const m = useMutation({
    mutationFn: async () => (await apiClient.post(`/api/ai-proposals/${proposal.id}/${mode}`,
      mode === 'adopt' ? { note: text } : { reason: text })).data,
    onSuccess: () => {
      toast.success(mode === 'adopt' ? '채택했습니다 — 이제 결재를 요청할 수 있습니다' : '제안을 폐기했습니다')
      setMode(null); setText(''); onDone()
    },
    onError: (e) => toast.error(errDetail(e, '처리하지 못했습니다')),
  })
  const adjusted = proposal.basis.adjusted ?? []

  if (proposal.status !== 'proposed') {
    return (
      <p className="flex flex-wrap items-center gap-1.5 rounded-md bg-muted/60 px-3 py-2 text-xs text-muted-foreground">
        <Sparkles className="h-3.5 w-3.5" />
        AI 제안 → {proposal.status === 'adopted'
          ? `${proposal.adopted_by ?? '—'} 채택(${proposal.adopted_changes?.length ? `${proposal.adopted_changes.length}건 수정 후` : '변경 없이'})`
          : `${proposal.status_label}${proposal.decision_note ? ` — ${proposal.decision_note}` : ''}`}
        · {proposal.summary}
      </p>
    )
  }
  return (
    <div className="space-y-2 rounded-lg border border-violet-300/60 bg-violet-50 p-3 text-sm dark:border-violet-400/30 dark:bg-violet-950/30">
      <p className="flex items-center gap-1.5 font-semibold text-violet-900 dark:text-violet-200">
        <Sparkles className="h-4 w-4" /> AI 제안 — 검토 후 채택하세요
      </p>
      <p>{proposal.summary}</p>
      <p className="text-xs text-muted-foreground">계기: {proposal.trigger}</p>
      {adjusted.length > 0 && (
        <div className="text-xs">
          <button type="button" className="text-primary underline-offset-2 hover:underline" onClick={() => setShowBasis((v) => !v)}>
            {showBasis ? '조정 내역 접기' : `주말·공휴일 조정 ${adjusted.length}건 보기`}
          </button>
          {showBasis && (
            <ul className="mt-1 max-h-40 space-y-0.5 overflow-y-auto pl-4 text-muted-foreground">
              {adjusted.map((a, n) => (
                <li key={n} className="list-disc">{a.title} {a.which} {a.from} → {a.to}{a.reason ? ` (${a.reason})` : ''}</li>
              ))}
            </ul>
          )}
        </div>
      )}
      <p className="text-xs text-muted-foreground">
        아래 표·간트에서 먼저 고친 뒤 채택해도 됩니다. 채택한 사람이 작성 책임자가 되며, 채택 전에는 결재를 요청할 수 없습니다.
      </p>
      {canDecide && (mode === null ? (
        <div className="flex gap-2">
          <Button size="sm" onClick={() => setMode('adopt')}>채택</Button>
          <Button size="sm" variant="outline" onClick={() => setMode('discard')}>폐기</Button>
        </div>
      ) : (
        <div className="space-y-2">
          <Textarea rows={2} value={text} onChange={(e) => setText(e.target.value)}
            placeholder={mode === 'adopt' ? '검토 의견(선택)' : '폐기 사유(필수) — 폐기하면 이 초안도 지워집니다'} />
          <div className="flex gap-2">
            <Button size="sm" disabled={m.isPending || (mode === 'discard' && !text.trim())} onClick={() => m.mutate()}>
              {mode === 'adopt' ? '채택 확정' : '폐기 확정'}
            </Button>
            <Button size="sm" variant="ghost" onClick={() => { setMode(null); setText('') }}>취소</Button>
          </div>
        </div>
      ))}
    </div>
  )
}
