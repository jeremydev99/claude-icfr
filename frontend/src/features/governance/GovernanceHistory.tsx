import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { History, Loader2 } from 'lucide-react'
import apiClient from '@/lib/axios'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { EVENT_LABELS, formatValues } from './governance.pure'
import type { GovernanceEvent } from './types'

/** 변경·결재 이력 — 지울 수 없는 기록(ADR-0038 §2.4). 접어 두었다가 펼칠 때 불러온다. */
export default function GovernanceHistory({ url, refreshKey }: { url: string; refreshKey?: unknown }) {
  const [open, setOpen] = useState(false)
  const [onlyDecisions, setOnlyDecisions] = useState(false)
  const { data = [], isLoading } = useQuery({
    queryKey: ['governance-events', url, refreshKey],
    queryFn: async () => (await apiClient.get<GovernanceEvent[]>(url)).data,
    enabled: open,
  })
  const rows = onlyDecisions ? data.filter((e) => !['value_change', 'item_confirm', 'item_unconfirm'].includes(e.action)) : data
  return (
    <div className="rounded-xl border bg-card shadow-card">
      <button type="button" onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center gap-2 px-5 py-4 text-left text-base font-semibold">
        <History className="h-4 w-4" /> 변경·결재 이력
        <span className="ml-auto text-sm font-normal text-muted-foreground">{open ? '접기' : '펼치기'}</span>
      </button>
      {open && (
        <div className="space-y-2 border-t px-5 pb-5 pt-3">
          <div className="flex items-center justify-between text-xs text-muted-foreground">
            <span>누가·언제·무엇을 바꿨는지 — 이 기록은 수정·삭제할 수 없습니다</span>
            <Button size="sm" variant="ghost" onClick={() => setOnlyDecisions((v) => !v)}>
              {onlyDecisions ? '전체 보기' : '결재만 보기'}
            </Button>
          </div>
          {isLoading ? (
            <div className="flex items-center gap-2 text-sm text-muted-foreground"><Loader2 className="h-4 w-4 animate-spin" />불러오는 중…</div>
          ) : rows.length === 0 ? (
            <p className="text-sm text-muted-foreground">기록이 없습니다.</p>
          ) : (
            <ul className="divide-y text-sm">
              {rows.map((e) => (
                <li key={e.id} className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5 py-2">
                  <span className="w-36 shrink-0 tabular text-xs text-muted-foreground">{new Date(e.created_at).toLocaleString('ko-KR')}</span>
                  <Badge variant="outline">{EVENT_LABELS[e.action] ?? e.action}</Badge>
                  {e.version != null && <span className="text-xs text-muted-foreground">v{e.version}</span>}
                  <span className="font-medium">{e.actor?.name ?? '시스템'}</span>
                  {e.target && <span className="text-muted-foreground">{e.target}</span>}
                  {e.reason && <span>「{e.reason}」</span>}
                  {(e.before || e.after) && (
                    <span className="basis-full pl-[9.5rem] text-xs text-muted-foreground">
                      {e.before && <>이전 {formatValues(e.before)}</>}{e.before && e.after && ' → '}{e.after && <>이후 {formatValues(e.after)}</>}
                    </span>
                  )}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  )
}
