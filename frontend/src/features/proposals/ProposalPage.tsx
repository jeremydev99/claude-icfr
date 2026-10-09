import { useMemo, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { ArrowLeft, Check, ChevronRight, CircleDot, Loader2, Lock, Pencil, X } from 'lucide-react'
import apiClient from '@/lib/axios'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle, DialogDescription } from '@/components/ui/dialog'
import { cn } from '@/lib/utils'
import GovernanceHistory from '@/features/governance/GovernanceHistory'
import { DECISION_LABEL, decisionCounts, proposerLabel, type Proposal, type ProposalItem } from './proposals.pure'
import HelpButton from '@/features/help/HelpButton'

const errorDetail = (e: unknown, f: string) =>
  (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? f

/** 제안 결재 화면 — 1차(책임관리자) 항목별 결정 → 검토 완료 → 2차(마스터) 승인. 버튼은 서버가 준 `can` 만 본다. */
export default function ProposalPage() {
  const { id } = useParams<{ id: string }>()
  const qc = useQueryClient()
  const { data: p, isLoading } = useQuery({
    queryKey: ['proposal', id],
    queryFn: async () => (await apiClient.get<Proposal>(`/api/proposals/${id}`)).data,
    enabled: !!id,
  })
  const m = useMutation({
    mutationFn: async ({ path, body }: { path: string; body?: unknown }) =>
      (await apiClient.post<Proposal>(`/api/proposals/${id}${path}`, body ?? {})).data,
    onSuccess: (d) => { qc.setQueryData(['proposal', id], d); qc.invalidateQueries({ queryKey: ['governance-inbox'] }) },
    onError: (e) => toast.error(errorDetail(e, '처리하지 못했습니다')),
  })
  const [modify, setModify] = useState<ProposalItem | null>(null)
  const [reasonFor, setReasonFor] = useState<'return' | 'approve' | null>(null)
  const [filter, setFilter] = useState<'all' | 'pending'>('all')

  if (isLoading || !p) {
    return <div className="flex items-center gap-2 p-8 text-muted-foreground"><Loader2 className="h-4 w-4 animate-spin" />불러오는 중…</div>
  }
  const c = p.can
  const counts = decisionCounts(p.items)
  const rows = filter === 'pending' ? p.items.filter((i) => i.decision === 'pending') : p.items
  const isLink = p.kind === 'control_link'
  const steps = [
    { label: p.requested_by ? `검토 요청 · ${p.requested_by.name}` : `제안 · ${proposerLabel(p.proposed_by)}`, done: true },
    { label: `1차 승인 · 책임관리자${p.reviewed_by ? ` (${p.reviewed_by.name})` : ''}`, done: !!p.reviewed_by, current: p.status === 'pending_review' },
    { label: `2차 승인 · 마스터관리자${p.approved_by ? ` (${p.approved_by.name})` : ''}`, done: p.status === 'approved', current: p.status === 'reviewed' },
  ]

  return (
    <div className="mx-auto max-w-[1400px] space-y-6 p-6 md:p-8">
      <div>
        <Link to={isLink ? '/rcm/links' : '/financial-statements'} className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
          <ArrowLeft className="h-4 w-4" />{isLink ? '통제 ↔ 계정 연결' : '재무제표'}
        </Link>
        <h1 className="mt-2 text-2xl font-bold tracking-tight">{p.title}</h1>
        {p.summary && <p className="mt-1 whitespace-pre-line text-sm text-muted-foreground">{p.summary}</p>}
      </div>

      <section className="space-y-3 rounded-xl border bg-card p-5 shadow-card">
        <div className="flex flex-wrap items-center gap-2">
          <span className="font-semibold">결재선</span>
          <HelpButton k="screen.proposals.approval-line" />
          <Badge variant={p.status === 'approved' ? 'default' : p.status === 'returned' ? 'destructive' : 'secondary'}>{p.status_label}</Badge>
          <span className="text-sm text-muted-foreground">
            항목 {counts.total} · 승인 {counts.accepted} · 변경 {counts.modified} · 반려 {counts.rejected} · 미결정 {counts.pending}
          </span>
        </div>
        <ol className="flex flex-wrap items-center gap-1.5 text-sm">
          {steps.map((s, i) => (
            <li key={s.label} className="flex items-center gap-1.5">
              {i > 0 && <ChevronRight className="h-4 w-4 text-muted-foreground" />}
              <span className={cn('inline-flex items-center gap-1.5 rounded-full border px-3 py-1',
                s.done && 'border-success/40 bg-success/10 text-success',
                s.current && 'border-primary/40 bg-accent font-semibold text-accent-foreground',
                !s.done && !s.current && 'text-muted-foreground')}>
                {s.done ? <Check className="h-3.5 w-3.5" /> : <CircleDot className="h-3.5 w-3.5" />}{s.label}
              </span>
            </li>
          ))}
        </ol>
        {p.closed_reason && <p className="text-sm text-destructive">반려 사유: {p.closed_reason}</p>}
        {p.result && isLink && (
          <p className="text-sm">반영 결과: 연결 {String(p.result.linked ?? 0)}건 · 해제 {String(p.result.unlinked ?? 0)}건 · 반려 {String(p.result.rejected ?? 0)}건</p>
        )}
        {p.result && !isLink && (
          <p className="text-sm">반영 결과: 연결 {String(p.result.linked ?? 0)}건
            {p.result.scoping_reloaded ? ` · 스코핑 다시 불러옴(계정 ${String(p.result.scoping_rows)}행, 템플릿 연결 ${String(p.result.scoping_linked)}행)` : ''}
            {p.result.scoping_note ? ` · ${String(p.result.scoping_note)}` : ''}</p>
        )}
        <div className="flex flex-wrap items-center gap-2">
          {c?.decide && counts.pending > 0 && (
            <Button size="sm" variant="outline" disabled={m.isPending}
              onClick={() => { if (window.confirm(`미결정 ${counts.pending}개 항목을 모두 승인할까요? 항목별 이력은 그대로 남습니다.`)) m.mutate({ path: '/decide-pending', body: { decision: 'accepted' } }) }}>
              남은 {counts.pending}개 모두 승인
            </Button>
          )}
          {c?.review_done && <Button size="sm" disabled={m.isPending} onClick={() => m.mutate({ path: '/review-done' })}>1차 검토 완료</Button>}
          {c?.approve && <Button size="sm" disabled={m.isPending} onClick={() => setReasonFor('approve')}>2차 승인·반영</Button>}
          {c?.return_ && <Button size="sm" variant="outline" disabled={m.isPending} onClick={() => setReasonFor('return')}>묶음 반려</Button>}
          {c && Object.values(c.why).length > 0 && (
            <span className="flex items-center gap-1 text-xs text-muted-foreground"><Lock className="h-3.5 w-3.5" />{Object.values(c.why).join(' · ')}</span>
          )}
        </div>
      </section>

      <section className="space-y-2">
        <div className="flex items-center justify-between">
          <h2 className="flex items-center gap-1 text-base font-semibold">제안 항목 <HelpButton k="screen.proposals.items" /></h2>
          <div className="flex gap-1">
            <Button size="sm" variant={filter === 'all' ? 'default' : 'ghost'} onClick={() => setFilter('all')}>전체</Button>
            <Button size="sm" variant={filter === 'pending' ? 'default' : 'ghost'} onClick={() => setFilter('pending')}>미결정만</Button>
          </div>
        </div>
        <ul className="space-y-2">
          {rows.map((i) => (
            <li key={i.id} className="rounded-xl border bg-card p-4 shadow-card">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0 space-y-1">
                  {isLink ? (
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge variant={i.action === 'link_remove' ? 'destructive' : 'outline'}>{i.action === 'link_remove' ? '해제' : '연결'}</Badge>
                    <span className="font-mono text-xs text-muted-foreground">{i.control_code}</span>
                    <span className="font-semibold">{i.control_name}</span>
                    <span className="text-muted-foreground">{i.action === 'link_remove' ? '✕' : '↔'}</span>
                    <Badge variant="outline">{i.statement_type}</Badge>
                    <span className="font-semibold text-primary">{i.account_name}</span>
                  </div>
                  ) : (
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge variant="outline">{i.statement_type}</Badge>
                    <span className="text-xs text-muted-foreground">{i.group_label}</span>
                    <span className="font-semibold">{i.account_name}</span>
                    <span className="text-muted-foreground">→</span>
                    {i.action === 'link'
                      ? <span className="font-semibold text-primary">{i.final_template_name ?? i.template_name}</span>
                      : <span className="font-semibold text-warning">대응 템플릿 없음 · 직접 평가</span>}
                    {i.decision === 'modified' && <span className="text-xs text-muted-foreground line-through">{i.template_name}</span>}
                  </div>
                  )}
                  <p className="text-sm text-muted-foreground">근거: {i.rationale}</p>
                  {i.decided_by && (
                    <p className="text-xs text-muted-foreground">
                      {DECISION_LABEL[i.decision]} · {i.decided_by.name}{i.decision_note ? ` · 「${i.decision_note}」` : ''}
                    </p>
                  )}
                </div>
                <div className="flex shrink-0 items-center gap-1.5">
                  <Badge variant={i.decision === 'rejected' ? 'destructive' : i.decision === 'pending' ? 'secondary' : 'default'}>
                    {DECISION_LABEL[i.decision]}
                  </Badge>
                  {c?.decide && (<>
                    <Button size="sm" variant="outline" disabled={m.isPending} title="승인"
                      onClick={() => m.mutate({ path: `/items/${i.id}/decide`, body: { decision: 'accepted' } })}><Check className="h-4 w-4" /></Button>
                    {i.action === 'link' && <Button size="sm" variant="outline" disabled={m.isPending} title="다른 템플릿 계정으로 변경"
                      onClick={() => setModify(i)}><Pencil className="h-4 w-4" /></Button>}
                    <Button size="sm" variant="outline" disabled={m.isPending} title="반려"
                      onClick={() => m.mutate({ path: `/items/${i.id}/decide`, body: { decision: 'rejected' } })}><X className="h-4 w-4" /></Button>
                  </>)}
                </div>
              </div>
            </li>
          ))}
        </ul>
      </section>

      <GovernanceHistory url={`/api/proposals/${p.id}/events`} refreshKey={`${p.status}-${counts.pending}`} />

      <ModifyDialog item={modify} onClose={() => setModify(null)}
        onPick={(tid, note) => { m.mutate({ path: `/items/${modify!.id}/decide`, body: { decision: 'modified', template_account_id: tid, note } }); setModify(null) }} />
      <ReasonDialog kind={reasonFor} isLink={isLink} onClose={() => setReasonFor(null)}
        onOk={(r) => { m.mutate({ path: reasonFor === 'approve' ? '/approve' : '/return', body: { reason: r } }); setReasonFor(null) }} />
    </div>
  )
}

function ModifyDialog({ item, onClose, onPick }: { item: ProposalItem | null; onClose: () => void; onPick: (tid: string, note: string) => void }) {
  const [q, setQ] = useState('')
  const [note, setNote] = useState('')
  const { data } = useQuery({
    queryKey: ['template-accounts', item?.statement_type],
    queryFn: async () => (await apiClient.get<{ template_accounts: { id: string; name: string; group_label: string | null }[] }>(
      '/api/fs/template-matches', { params: { statement_type: item!.statement_type } })).data.template_accounts,
    enabled: !!item?.statement_type,
  })
  const list = useMemo(() => (data ?? []).filter((t) => !q || t.name.includes(q) || (t.group_label ?? '').includes(q)), [data, q])
  return (
    <Dialog open={!!item} onOpenChange={(o) => { if (!o) { setQ(''); setNote(''); onClose() } }}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>{item?.account_name} — 다른 템플릿 계정으로 변경</DialogTitle>
          <DialogDescription>연결할 템플릿 계정을 고르세요. 변경 사유는 이력에 남습니다.</DialogDescription>
        </DialogHeader>
        <input className="h-9 w-full rounded-md border px-3 text-sm" placeholder="계정 이름 검색" value={q} onChange={(e) => setQ(e.target.value)} />
        <Textarea placeholder="변경 사유 (선택)" rows={2} value={note} onChange={(e) => setNote(e.target.value)} />
        <ul className="max-h-72 space-y-1 overflow-y-auto">
          {list.map((t) => (
            <li key={t.id}>
              <button type="button" className="w-full rounded-md border px-3 py-2 text-left text-sm hover:border-primary/40 hover:bg-accent"
                onClick={() => onPick(t.id, note)}>
                <span className="text-xs text-muted-foreground">{t.group_label}</span> <b>{t.name}</b>
              </button>
            </li>
          ))}
        </ul>
      </DialogContent>
    </Dialog>
  )
}

function ReasonDialog({ kind, isLink = false, onClose, onOk }: { kind: 'return' | 'approve' | null; isLink?: boolean; onClose: () => void; onOk: (r: string) => void }) {
  const [text, setText] = useState('')
  const required = kind === 'return'
  return (
    <Dialog open={!!kind} onOpenChange={(o) => { if (!o) { setText(''); onClose() } }}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>{kind === 'approve' ? '2차 승인·반영' : '묶음 반려'}</DialogTitle>
          <DialogDescription>
            {kind === 'approve'
              ? (isLink ? '승인하면 승인된 연결이 확정되고(커버리지 "확정"), 반려된 항목은 빠집니다.' : '승인하면 승인·변경된 항목의 연결이 실제로 저장되고, 작성 중인 스코핑을 다시 불러옵니다.')
              : (isLink ? '반려하면 묶음이 닫히고 연결들은 작성 중(초안)으로 돌아갑니다 — 고쳐서 다시 요청합니다.' : '반려하면 이 제안 묶음은 닫힙니다.')}
          </DialogDescription>
        </DialogHeader>
        <Textarea rows={3} placeholder={required ? '사유 (필수)' : '의견 (선택)'} value={text} onChange={(e) => setText(e.target.value)} />
        <DialogFooter>
          <Button variant="outline" onClick={() => { setText(''); onClose() }}>취소</Button>
          <Button disabled={required && !text.trim()} onClick={() => { onOk(text.trim()); setText('') }}>{kind === 'approve' ? '승인' : '반려'}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
