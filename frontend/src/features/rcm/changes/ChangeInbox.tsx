import { useState } from 'react'
import { toast } from 'sonner'
import { ArrowRight, Check, Inbox, Loader2, Send, Undo2, X } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { cn } from '@/lib/utils'
import { FIELD_LABEL, errText, showValue, useChangeAction, useChangeOverview, type ChangeBatch, type ControlChange } from './api'

const STATUS_TONE: Record<ControlChange['status'], string> = {
  draft: 'border-slate-300 text-slate-700', dept_review: 'border-amber-300 bg-amber-50 text-amber-800',
  dept_approved: 'border-sky-300 bg-sky-50 text-sky-800', in_batch: 'border-primary/40 bg-accent text-accent-foreground',
  applied: 'border-emerald-300 bg-emerald-50 text-emerald-800', rejected: 'border-rose-300 bg-rose-50 text-rose-700',
  withdrawn: 'border-slate-200 text-slate-500',
}

/**
 * 통제 변경 결재함(2026-10-06) — 임시저장 → 상신 → 조직장 → 내부회계 담당자 일괄 상신 → 내부회계관리자 → 반영.
 * 내가 할 일만 위에 모은다: 조직장 결재 · 내부회계 대기함(일괄 상신) · 관리자 결재, 아래는 내 변경.
 */
export default function ChangeInbox() {
  const { data, isLoading } = useChangeOverview()
  const act = useChangeAction()
  const [pick, setPick] = useState<Set<string>>(new Set())
  const [batchNote, setBatchNote] = useState('')
  const run = (url: string, body?: unknown, ok?: string) =>
    act.mutate({ method: 'post', url, body }, { onSuccess: () => ok && toast.success(ok), onError: (e) => toast.error(errText(e, '처리하지 못했습니다')) })

  if (isLoading || !data) return <div className="flex items-center gap-2 p-6 text-muted-foreground"><Loader2 className="h-4 w-4 animate-spin" />불러오는 중…</div>
  const reviewBatches = data.batches.filter((b) => b.status === 'review')
  const doneBatches = data.batches.filter((b) => b.status === 'done')

  return (
    <div className="space-y-6">
      <Flow />

      {data.dept.length > 0 && (
        <Section title="조직장 결재" count={data.dept.length} hint="내 부서 통제의 변경 — 승인하면 내부회계 대기함으로 갑니다">
          {data.dept.map((c) => (
            <ChangeCard key={c.id} c={c} actions={<DeptActions c={c} onRun={run} busy={act.isPending} />} />
          ))}
        </Section>
      )}

      {data.can.batch_submit && (
        <Section title="내부회계 대기함" count={data.queue.length} hint="조직장 승인이 끝난 변경 — 골라서 내부회계관리자에게 일괄 상신합니다">
          {data.queue.length === 0 ? <Empty text="대기 중인 변경이 없습니다" /> : (
            <>
              <div className="flex flex-wrap items-center gap-2 rounded-lg border bg-muted/40 p-2">
                <label className="flex items-center gap-1.5 px-1 text-sm">
                  <input type="checkbox" checked={pick.size === data.queue.length}
                    onChange={() => setPick(pick.size === data.queue.length ? new Set() : new Set(data.queue.map((c) => c.id)))} />
                  전체 선택
                </label>
                <input value={batchNote} onChange={(e) => setBatchNote(e.target.value)} placeholder="상신 메모(선택)"
                  className="h-8 min-w-0 flex-1 rounded-md border bg-background px-2 text-sm" />
                <Button size="sm" disabled={!pick.size || act.isPending} onClick={() => act.mutate(
                  { method: 'post', url: '/api/rcm-changes/batches', body: { change_ids: [...pick], note: batchNote || null } },
                  { onSuccess: () => { toast.success(`${pick.size}건을 일괄 상신했습니다`); setPick(new Set()); setBatchNote('') },
                    onError: (e) => toast.error(errText(e, '상신하지 못했습니다')) },
                )}><Send className="mr-1.5 h-4 w-4" />선택 {pick.size}건 일괄 상신</Button>
              </div>
              {data.queue.map((c) => (
                <ChangeCard key={c.id} c={c} lead={
                  <input type="checkbox" className="mt-1" checked={pick.has(c.id)} aria-label={`${c.control_code} 선택`}
                    onChange={() => { const n = new Set(pick); if (n.has(c.id)) n.delete(c.id); else n.add(c.id); setPick(n) }} />
                } />
              ))}
            </>
          )}
        </Section>
      )}

      {reviewBatches.length > 0 && (
        <Section title="내부회계관리자 결재" count={reviewBatches.length} hint="항목마다 승인 또는 반려(사유)를 고른 뒤 결재합니다. 승인 항목만 RCM 에 반영됩니다">
          {reviewBatches.map((b) => <BatchCard key={b.id} b={b} />)}
        </Section>
      )}

      <Section title="내 변경" count={data.mine.filter((c) => !['applied', 'withdrawn'].includes(c.status)).length}
        hint="통제 편집에서 임시저장한 변경 — 상신해야 결재가 시작됩니다">
        {data.mine.length === 0 ? <Empty text="통제 편집 창에서 고친 뒤 [임시저장]하면 여기에 모입니다" /> : data.mine.map((c) => (
          <ChangeCard key={c.id} c={c} actions={
            <div className="flex gap-1.5">
              {['draft', 'rejected'].includes(c.status) && <Button size="sm" disabled={act.isPending} onClick={() => run(`/api/rcm-changes/${c.id}/submit`, undefined, '상신했습니다')}><Send className="mr-1 h-3.5 w-3.5" />상신</Button>}
              {['draft', 'dept_review', 'rejected'].includes(c.status) && <Button size="sm" variant="ghost" disabled={act.isPending}
                onClick={() => { if (window.confirm('이 변경을 회수할까요? 고친 내용은 반영되지 않습니다.')) run(`/api/rcm-changes/${c.id}/withdraw`, undefined, '회수했습니다') }}><Undo2 className="mr-1 h-3.5 w-3.5" />회수</Button>}
            </div>
          } />
        ))}
      </Section>

      {doneBatches.length > 0 && (
        <details className="rounded-lg border px-4 py-3 text-sm">
          <summary className="cursor-pointer font-medium">최근 결재 완료 {doneBatches.length}건</summary>
          <ul className="mt-2 space-y-1 text-muted-foreground">
            {doneBatches.map((b) => (
              <li key={b.id}>{b.decided_at?.slice(0, 16).replace('T', ' ')} · {b.decided_by} 결재 · 반영 {b.result?.applied ?? 0} · 반려 {b.result?.rejected ?? 0} (상신 {b.submitted_by})</li>
            ))}
          </ul>
        </details>
      )}
    </div>
  )
}

function Flow() {
  const steps = ['작성자 임시저장·상신', '조직장 승인', '내부회계 담당자 일괄 상신', '내부회계관리자 승인', 'RCM 반영']
  return (
    <ol className="flex flex-wrap items-center gap-1.5 text-xs text-muted-foreground">
      {steps.map((s, i) => (
        <li key={s} className="flex items-center gap-1.5">
          {i > 0 && <ArrowRight className="h-3.5 w-3.5" />}
          <span className="rounded-full border bg-card px-2.5 py-1">{s}</span>
        </li>
      ))}
      <li className="ml-2">· 반려는 어느 단계든 작성자에게 돌아갑니다</li>
    </ol>
  )
}

function Section({ title, count, hint, children }: { title: string; count: number; hint: string; children: React.ReactNode }) {
  return (
    <section className="space-y-2">
      <h3 className="flex flex-wrap items-baseline gap-2 text-base font-semibold">
        {title}<span className="text-sm font-normal text-muted-foreground">{count}건 — {hint}</span>
      </h3>
      <div className="space-y-2">{children}</div>
    </section>
  )
}

function Empty({ text }: { text: string }) {
  return <p className="flex items-center gap-2 rounded-lg border border-dashed p-4 text-sm text-muted-foreground"><Inbox className="h-4 w-4" />{text}</p>
}

function Diff({ c }: { c: ControlChange }) {
  return (
    <table className="mt-2 w-full text-sm">
      <tbody>
        {Object.entries(c.changes).map(([k, v]) => (
          <tr key={k} className="border-t align-top">
            <td className="w-32 py-1.5 pr-2 text-xs text-muted-foreground">{FIELD_LABEL[k] ?? k}</td>
            <td className="py-1.5 pr-2 text-muted-foreground line-through decoration-rose-400/70">{showValue(c.before[k])}</td>
            <td className="py-1.5 font-medium text-emerald-800 dark:text-emerald-300">{showValue(v)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

function ChangeCard({ c, actions, lead }: { c: ControlChange; actions?: React.ReactNode; lead?: React.ReactNode }) {
  const reason = c.status === 'rejected' ? (c.rejected_by === 'dept' ? c.dept_note : c.admin_note) : null
  return (
    <div className="flex gap-3 rounded-xl border bg-card p-3 shadow-card">
      {lead}
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <span className="font-mono text-xs text-muted-foreground">{c.control_code}</span>
          <span className="font-medium">{c.control_name}</span>
          <Badge variant="outline" className={cn('text-[11px]', STATUS_TONE[c.status])}>{c.status_label}</Badge>
          <span className="text-xs text-muted-foreground">작성 {c.author}{c.dept_approver ? ` · 조직장 ${c.dept_approver}` : ''}{c.dept_skipped ? ` · ${c.dept_skipped}` : ''}</span>
          <span className="ml-auto">{actions}</span>
        </div>
        {c.note && <p className="mt-1 text-xs text-muted-foreground">메모: {c.note}</p>}
        {reason && <p className="mt-1 text-xs text-rose-700">반려 사유: {reason}</p>}
        <Diff c={c} />
      </div>
    </div>
  )
}

function DeptActions({ c, onRun, busy }: { c: ControlChange; onRun: (url: string, body?: unknown, ok?: string) => void; busy: boolean }) {
  const [note, setNote] = useState('')
  const [rejecting, setRejecting] = useState(false)
  if (!c.can_dept_decide) return null
  return rejecting ? (
    <span className="flex items-center gap-1.5">
      <input value={note} onChange={(e) => setNote(e.target.value)} placeholder="반려 사유" className="h-8 w-48 rounded-md border bg-background px-2 text-sm" autoFocus />
      <Button size="sm" variant="destructive" disabled={!note.trim() || busy} onClick={() => onRun(`/api/rcm-changes/${c.id}/dept-reject`, { note }, '반려했습니다')}>반려</Button>
      <Button size="sm" variant="ghost" onClick={() => setRejecting(false)}>취소</Button>
    </span>
  ) : (
    <span className="flex gap-1.5">
      <Button size="sm" disabled={busy} onClick={() => onRun(`/api/rcm-changes/${c.id}/dept-approve`, {}, '승인했습니다')}><Check className="mr-1 h-3.5 w-3.5" />승인</Button>
      <Button size="sm" variant="outline" disabled={busy} onClick={() => setRejecting(true)}><X className="mr-1 h-3.5 w-3.5" />반려</Button>
    </span>
  )
}

function BatchCard({ b }: { b: ChangeBatch }) {
  const act = useChangeAction()
  const [dec, setDec] = useState<Record<string, { approve: boolean; note: string }>>(
    () => Object.fromEntries(b.items.map((i) => [i.id, { approve: true, note: '' }])))
  const [note, setNote] = useState('')
  const missing = b.items.filter((i) => !dec[i.id]?.approve && !dec[i.id]?.note.trim()).length
  return (
    <div className="space-y-2 rounded-xl border bg-card p-4 shadow-card">
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <Badge>결재 대기</Badge>
        <span>상신 {b.submitted_by} · {b.created_at.slice(0, 16).replace('T', ' ')} · {b.item_count}건</span>
        {b.note && <span className="text-muted-foreground">— {b.note}</span>}
      </div>
      {b.items.map((i) => (
        <ChangeCard key={i.id} c={i} actions={b.can_decide && (
          <span className="flex items-center gap-1.5">
            <Button size="sm" variant={dec[i.id]?.approve ? 'default' : 'outline'} onClick={() => setDec({ ...dec, [i.id]: { ...dec[i.id], approve: true } })}>승인</Button>
            <Button size="sm" variant={!dec[i.id]?.approve ? 'destructive' : 'outline'} onClick={() => setDec({ ...dec, [i.id]: { ...dec[i.id], approve: false } })}>반려</Button>
            {!dec[i.id]?.approve && (
              <input value={dec[i.id]?.note ?? ''} onChange={(e) => setDec({ ...dec, [i.id]: { approve: false, note: e.target.value } })}
                placeholder="반려 사유(필수)" className="h-8 w-44 rounded-md border bg-background px-2 text-sm" />
            )}
          </span>
        )} />
      ))}
      {b.can_decide ? (
        <div className="flex flex-wrap items-end gap-2 border-t pt-3">
          <Textarea rows={1} value={note} onChange={(e) => setNote(e.target.value)} placeholder="결재 의견(선택)" className="min-h-9 flex-1" />
          <Button disabled={missing > 0 || act.isPending} onClick={() => act.mutate(
            { method: 'post', url: `/api/rcm-changes/batches/${b.id}/decide`,
              body: { decisions: b.items.map((i) => ({ id: i.id, approve: dec[i.id].approve, note: dec[i.id].note || null })), note: note || null } },
            { onSuccess: (r) => { const x = r as { applied: number; rejected: number }; toast.success(`결재했습니다 — 반영 ${x.applied}건 · 반려 ${x.rejected}건`) },
              onError: (e) => toast.error(errText(e, '결재하지 못했습니다')) },
          )}>{missing > 0 ? `반려 사유 ${missing}건 필요` : '결재(승인 항목 반영)'}</Button>
        </div>
      ) : <p className="text-xs text-muted-foreground">내부회계관리자가 결재합니다(상신한 본인은 결재할 수 없습니다).</p>}
    </div>
  )
}
