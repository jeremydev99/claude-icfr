import { useEffect, useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Loader2 } from 'lucide-react'
import apiClient from '@/lib/axios'
import { useActiveTenantId } from '@/features/auth/store'
import { Badge } from '@/components/ui/badge'
import type { RcmYear } from './RcmYearView'

type Item = { id: string; code: string | null; title: string }
type Change = { field: string; label: string; before: unknown; after: unknown; added?: string[]; removed?: string[] }
type Changed = Item & { changes: Change[] }
type Layer = { added: Item[]; removed: Item[]; changed: Changed[] }
interface CompareResult {
  base: string
  target: string
  summary_text: string
  total: number
  summary: Record<string, { added: number; removed: number; changed: number }>
  layers: Record<string, Layer>
}

const LAYERS: [string, string][] = [['controls', '통제'], ['risks', '위험'], ['sub_processes', '하위프로세스'], ['processes', '프로세스']]

const show = (v: unknown) => (v === null || v === undefined || v === '' ? '(없음)' : typeof v === 'boolean' ? (v ? '예' : '아니오') : String(v))

/**
 * 확정본 비교(2026-10-08) — 확정본끼리(연도가 달라도 됨) 또는 확정본 ↔ 현재 RCM.
 * 요약 건수가 먼저, 펼치면 통제별로 무엇이 전→후로 바뀌었는지.
 */
export default function RcmCompare({ years }: { years: RcmYear[] }) {
  const tenantId = useActiveTenantId()
  const options = useMemo(() => [
    ...years.flatMap((y) => y.snapshots.map((s) => ({ value: `${y.id}:${s.version}`, label: `${y.fiscal_year} v${s.version} (${s.confirmed_at.slice(0, 10)})` }))),
    { value: 'live', label: '현재 RCM' },
  ], [years])
  const [base, setBase] = useState('')
  const [target, setTarget] = useState('live')
  useEffect(() => {
    if (!base && options.length > 1) setBase(options[0].value)   // 기본: 가장 최근 확정본 ↔ 현재 RCM
  }, [options, base])

  const { data, isFetching, error } = useQuery({
    queryKey: ['rcm-compare', tenantId, base, target],
    queryFn: async () => (await apiClient.get<CompareResult>('/api/rcm-years/compare', { params: { base, target } })).data,
    enabled: Boolean(base) && base !== target,
  })

  if (options.length < 2) return null   // 확정본이 하나도 없으면 비교할 것이 없다
  const select = (id: string, value: string, set: (v: string) => void, label: string) => (
    <select id={id} value={value} onChange={(e) => set(e.target.value)} aria-label={label}
      className="h-8 rounded border bg-background px-2 text-sm">
      {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
    </select>
  )

  return (
    <div className="space-y-3 rounded-xl border bg-card p-4 shadow-card">
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <span className="font-semibold">확정본 비교</span>
        {select('rcm-compare-base', base, setBase, '기준')}
        <span className="text-muted-foreground">→</span>
        {select('rcm-compare-target', target, setTarget, '대상')}
        {isFetching && <Loader2 className="h-4 w-4 animate-spin" />}
      </div>
      {base === target && <p className="text-sm text-muted-foreground">기준과 대상을 다르게 고르세요.</p>}
      {error && <p className="text-sm text-destructive">비교하지 못했습니다.</p>}
      {data && base !== target && (
        <>
          <p className="text-sm"><b>{data.base}</b> → <b>{data.target}</b>: {data.summary_text}</p>
          {LAYERS.map(([key, label]) => {
            const l = data.layers[key]
            const s = data.summary[key]
            if (!s.added && !s.removed && !s.changed) return null
            return (
              <details key={key} className="rounded-md border p-3 text-sm" open={key === 'controls'}>
                <summary className="cursor-pointer font-medium">
                  {label} <span className="tabular-nums text-muted-foreground">변경 {s.changed} · 추가 {s.added} · 삭제 {s.removed}</span>
                </summary>
                <div className="mt-2 space-y-2">
                  {l.added.map((i) => (
                    <div key={i.id} className="flex flex-wrap gap-2"><Badge className="bg-success/15 text-success">추가</Badge>
                      <span className="font-mono">{i.code}</span><span>{i.title}</span></div>
                  ))}
                  {l.removed.map((i) => (
                    <div key={i.id} className="flex flex-wrap gap-2"><Badge variant="destructive">삭제</Badge>
                      <span className="font-mono">{i.code}</span><span className="line-through">{i.title}</span></div>
                  ))}
                  {l.changed.map((i) => (
                    <div key={i.id} className="rounded bg-muted/40 p-2">
                      <div className="flex flex-wrap gap-2"><Badge variant="outline">변경</Badge>
                        <span className="font-mono">{i.code}</span><span>{i.title}</span></div>
                      <ul className="mt-1 space-y-0.5 pl-4 text-xs">
                        {i.changes.map((c) => (
                          <li key={c.field} className="min-w-0 break-words">
                            <span className="text-muted-foreground">{c.label}: </span>
                            {c.added || c.removed
                              ? <>{c.added?.length ? `+${c.added.join(', ')} ` : ''}{c.removed?.length ? `−${c.removed.join(', ')}` : ''}</>
                              : <><span className="line-through opacity-70">{show(c.before)}</span> → <b>{show(c.after)}</b></>}
                          </li>
                        ))}
                      </ul>
                    </div>
                  ))}
                </div>
              </details>
            )
          })}
        </>
      )}
    </div>
  )
}
