import { useState } from 'react'
import { toast } from 'sonner'
import { Loader2 } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { errorDetail, useFsSuspense, useFsWrite } from '../api/useFs'
import { formatAmount, reclassTargets } from '../fsTree.pure'
import type { AmountNode, SuspenseAction, SuspenseItem } from '../types'

const ACTION_LABEL: Record<SuspenseAction, string> = {
  fix_subtotal: '소계 정정',
  reclass: '계정 대체',
  accept: '사유와 함께 유지',
}

/**
 * 임시계정(원본 차이) 검토 (ADR-0037 §2.13) — 미해결이 있으면 확정할 수 없다.
 *
 * - 소계 정정: 원본 소계가 틀렸다 → 소계를 하위 합으로 고친다(원래 값은 기록)
 * - 계정 대체: 하위 계정 하나가 빠졌거나 틀렸다 → 차액을 같은 소계 아래 계정으로 옮긴다
 * - 사유와 함께 유지: 차이를 그대로 두되 검토했음을 남긴다
 * 해소하면 서버가 연쇄 차이를 다시 계산한다(윗 소계 임시계정이 저절로 사라질 수 있다).
 */
export default function SuspensePanel({ statementId, tree, canEdit, onSelect }: {
  statementId: string
  tree: AmountNode[]
  canEdit: boolean
  onSelect: (accountId: string) => void
}) {
  const { data: items } = useFsSuspense(statementId)
  const open = (items ?? []).filter((x) => !x.resolved)
  const done = (items ?? []).filter((x) => x.resolved)
  if (!items?.length) return null
  return (
    <div className="space-y-2 text-xs">
      {open.length > 0 ? (
        <p className="text-muted-foreground">
          원본 파일의 소계가 하위 합과 달라 차액을 <b>임시계정(원본 차이)</b>에 넣어 두었습니다. 원본 숫자는 바뀌지 않았습니다.
          검토 후 반영하세요 — 미해결 {open.length}건이 남아 있으면 확정할 수 없습니다.
        </p>
      ) : (
        <p className="text-muted-foreground">원본 차이는 모두 검토했습니다.</p>
      )}
      {open.map((x) => (
        <SuspenseRow key={x.amount_id} item={x} statementId={statementId} tree={tree} canEdit={canEdit}
          onSelect={onSelect} />
      ))}
      {done.length > 0 && (
        <details className="rounded border px-3 py-2">
          <summary className="cursor-pointer text-muted-foreground">해소 이력 {done.length}건</summary>
          <ul className="mt-2 space-y-1">
            {done.map((x) => (
              <li key={x.amount_id}>
                <Badge variant="secondary">{ACTION_LABEL[x.resolved!.action]}</Badge>
                <span className="ml-2">{x.parent_name}</span>
                <span className="ml-2 tabular-nums">{formatAmount(x.resolved!.amount)}</span>
                <span className="ml-2 text-muted-foreground">— {x.resolved!.reason} ({x.resolved!.at.slice(0, 16).replace('T', ' ')})</span>
              </li>
            ))}
          </ul>
        </details>
      )}
    </div>
  )
}

function SuspenseRow({ item, statementId, tree, canEdit, onSelect }: {
  item: SuspenseItem
  statementId: string
  tree: AmountNode[]
  canEdit: boolean
  onSelect: (accountId: string) => void
}) {
  const [reason, setReason] = useState('')
  const [target, setTarget] = useState('')
  const mutation = useFsWrite(statementId)
  const targets = reclassTargets(tree, item.parent_account_id)

  const run = (action: SuspenseAction) => {
    if (!reason.trim()) return toast.error('해소 사유를 입력하세요')
    if (action === 'reclass' && !target) return toast.error('옮길 계정을 고르세요')
    mutation.mutate(
      { kind: 'resolve', amountId: item.amount_id, action, reason: reason.trim(), targetAccountId: target || undefined },
      {
        onSuccess: () => toast.success(`${item.parent_name} — ${ACTION_LABEL[action]} 완료`),
        onError: (e) => toast.error(errorDetail(e, '해소하지 못했습니다')),
      },
    )
  }

  return (
    <div className="rounded border border-amber-300 bg-amber-50/50 p-3">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <button type="button" className="font-medium underline-offset-2 hover:underline"
          onClick={() => onSelect(item.account_id)}>
          {item.parent_name}
        </button>
        <span className="tabular-nums">
          원본 소계 {formatAmount(item.actual)} − 하위 합 {formatAmount(item.expected)} = 차액{' '}
          <b className="text-amber-800">{formatAmount(item.amount)}</b>
        </span>
      </div>
      {canEdit ? (
        <div className="mt-2 space-y-2">
          <Textarea value={reason} onChange={(e) => setReason(e.target.value)} rows={2}
            placeholder="해소 사유 (필수) — 예: 정산표 수식이 자본조정을 빠뜨림" className="text-xs" />
          <div className="flex flex-wrap items-center gap-2">
            <Button size="sm" variant="outline" disabled={mutation.isPending} onClick={() => run('fix_subtotal')}>
              소계를 하위 합으로 정정
            </Button>
            <select value={target} onChange={(e) => setTarget(e.target.value)}
              className="h-8 rounded border bg-background px-2 text-xs" disabled={!targets.length}>
              <option value="">옮길 계정 선택…</option>
              {targets.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
            </select>
            <Button size="sm" variant="outline" disabled={mutation.isPending || !targets.length}
              onClick={() => run('reclass')}>
              차액을 이 계정으로
            </Button>
            <Button size="sm" variant="ghost" disabled={mutation.isPending} onClick={() => run('accept')}>
              사유와 함께 유지
            </Button>
            {mutation.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
          </div>
        </div>
      ) : (
        <p className="mt-1 text-muted-foreground">내부회계관리자가 검토합니다(draft 상태에서만).</p>
      )}
    </div>
  )
}
