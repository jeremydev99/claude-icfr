import { Badge } from '@/components/ui/badge'

type Item = { id: string; code: string | null; title: string }
type Change = { field: string; label: string; before: unknown; after: unknown; added?: string[]; removed?: string[] }
type Changed = Item & { changes: Change[] }
type Layer = { added: Item[]; removed: Item[]; changed: Changed[] }
/** 백엔드 `services/rcm_diff.diff` 결과 — 확정본 비교와 엑셀 갱신 미리보기가 같이 쓴다. */
export interface RcmDiff {
  total: number
  summary: Record<string, { added: number; removed: number; changed: number }>
  layers: Record<string, Layer>
}

const LAYERS: [string, string][] = [['controls', '통제'], ['risks', '위험'], ['sub_processes', '하위프로세스'], ['processes', '프로세스']]

const show = (v: unknown) => (v === null || v === undefined || v === '' ? '(없음)' : typeof v === 'boolean' ? (v ? '예' : '아니오') : String(v))

/** 계층별 추가·삭제·변경 — 요약 건수, 펼치면 항목별 전→후. */
export default function RcmDiffView({ diff }: { diff: RcmDiff }) {
  return (
    <>
      {LAYERS.map(([key, label]) => {
        const l = diff.layers[key]
        const s = diff.summary[key]
        if (!s || (!s.added && !s.removed && !s.changed)) return null
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
  )
}
