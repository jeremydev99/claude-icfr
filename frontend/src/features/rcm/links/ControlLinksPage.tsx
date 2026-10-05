import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { toast } from 'sonner'
import { ArrowLeft, GitMerge, Grid3x3, Loader2, Search, Send, Sparkles, Star, Workflow } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Checkbox } from '@/components/ui/checkbox'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { cn } from '@/lib/utils'
import { useAuthStore } from '@/features/auth/store'
import { isIcfrStaffForUser } from '@/features/auth/permissions.pure'
import { errDetail, useAddLink, useAutoMatch, useBoard, useRemoveLink, useSubmitLinks } from './api'
import {
  MATCH_LABEL, accountCoverage, boardStats, buildMatrix, groupControls, indexLinks, linkLook, parentName,
  visibleAccounts, type Board, type BoardLink, type LinkLook,
} from './linkBoard.pure'

type Sel = { kind: 'control'; id: string } | { kind: 'account'; id: string } | null

const LOOK_STROKE: Record<LinkLook, { color: string; dash?: string; label: string }> = {
  active: { color: 'hsl(var(--primary))', label: '확정(승인됨)' },
  draft: { color: 'hsl(38 92% 45%)', dash: '6 4', label: '작성 중' },
  review: { color: 'hsl(var(--primary) / 0.55)', dash: '2 4', label: '결재 중' },
  removing: { color: 'hsl(350 75% 50%)', dash: '6 4', label: '해제 예정' },
}
const LOOK_CHIP: Record<LinkLook, string> = {
  active: 'bg-primary text-primary-foreground border-primary',
  draft: 'bg-amber-50 text-amber-800 border-amber-300 dark:bg-amber-950/40 dark:text-amber-200 dark:border-amber-700',
  review: 'bg-accent text-accent-foreground border-primary/30',
  removing: 'bg-rose-50 text-rose-700 border-rose-300 line-through dark:bg-rose-950/40 dark:text-rose-300',
}

/**
 * 통제 ↔ 계정 연결 (ADR-0040). 왼쪽 RCM 통제를 오른쪽 계정 위로 끌어다 놓아 잇는다(휴대폰: 통제 선택 → 계정 누르기).
 * 자동 매칭이 초안을 만들고, 실무자가 고친 뒤 "검토 요청" → 책임관리자 1차 → 마스터 2차 승인으로 확정된다.
 */
export default function ControlLinksPage() {
  const user = useAuthStore((s) => s.user)
  const canEdit = isIcfrStaffForUser(user) || user?.external?.user_type === 'advisor'
  const { data: board, isLoading } = useBoard()
  const [tab, setTab] = useState<'board' | 'matrix'>('board')
  const [sel, setSel] = useState<Sel>(null)
  const [submitOpen, setSubmitOpen] = useState(false)
  const auto = useAutoMatch()

  if (isLoading || !board) {
    return <div className="flex items-center gap-2 p-8 text-muted-foreground"><Loader2 className="h-4 w-4 animate-spin" />불러오는 중…</div>
  }
  const stats = boardStats(board)

  return (
    <div className="mx-auto max-w-[1600px] space-y-5 p-6 md:p-8">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <Link to="/rcm" className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
            <ArrowLeft className="h-4 w-4" />RCM 관리
          </Link>
          <h1 className="mt-1 flex items-center gap-2 text-2xl font-bold tracking-tight"><GitMerge className="h-6 w-6 text-primary" />통제 ↔ 계정 연결</h1>
          <p className="mt-1 max-w-3xl text-sm text-muted-foreground">
            자동 매칭이 RCM 관련 계정 표기로 초안을 만듭니다. 못 찾은 연결은 <b>왼쪽 통제를 오른쪽 계정 위로 끌어다 놓아</b> 잇고,
            "검토 요청"하면 책임관리자 1차 → 마스터 2차 승인으로 확정됩니다. 확정된 연결은 스코핑 커버리지의 근거가 됩니다.
          </p>
        </div>
        {canEdit && (
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" disabled={auto.isPending} onClick={() => auto.mutate(undefined, {
              onSuccess: (r) => toast.success(r.added ? `자동 매칭으로 초안 ${r.added}건을 만들었습니다` : '새로 찾은 연결이 없습니다'),
              onError: (e) => toast.error(errDetail(e, '자동 매칭에 실패했습니다')),
            })}>
              {auto.isPending ? <Loader2 className="mr-1.5 h-4 w-4 animate-spin" /> : <Sparkles className="mr-1.5 h-4 w-4" />}자동 매칭
            </Button>
            <Button disabled={stats.draft === 0 || !!board.open_proposal} onClick={() => setSubmitOpen(true)}>
              <Send className="mr-1.5 h-4 w-4" />검토 요청{stats.draft ? ` ${stats.draft}건` : ''}
            </Button>
          </div>
        )}
      </div>

      {/* 현황 */}
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Stat label="유의 계정" value={stats.significant} hint="최신 스코핑의 결론 Y" />
        <Stat label="통제 확정" value={stats.sigCovered} tone="ok" hint={`승인된 연결이 있는 유의 계정 · 전체 확정 연결 ${stats.active}건`} />
        <Stat label="작성·결재 중" value={stats.sigPending} tone="warn" hint={`초안 ${stats.draft}건 · 결재 중 ${stats.review}건`} />
        <Stat label="통제 없음" value={stats.sigNone} tone={stats.sigNone ? 'bad' : 'ok'} hint="연결이 하나도 없는 유의 계정" />
      </div>

      {board.open_proposal && (
        <div className="flex flex-wrap items-center gap-2 rounded-lg border border-primary/30 bg-accent px-4 py-2.5 text-sm">
          <Workflow className="h-4 w-4 text-primary" />
          <span>결재 중: <b>{board.open_proposal.title}</b> — 결재 중인 연결은 잠깁니다.</span>
          <Link to={`/proposals/${board.open_proposal.id}`} className="font-medium text-primary underline-offset-2 hover:underline">결재 화면으로</Link>
        </div>
      )}

      <div className="flex items-center gap-1 rounded-md border p-1 w-fit">
        <Button size="sm" variant={tab === 'board' ? 'default' : 'ghost'} onClick={() => setTab('board')}><GitMerge className="mr-1.5 h-4 w-4" />연결 보드</Button>
        <Button size="sm" variant={tab === 'matrix' ? 'default' : 'ghost'} onClick={() => setTab('matrix')}><Grid3x3 className="mr-1.5 h-4 w-4" />매트릭스</Button>
      </div>

      {tab === 'board'
        ? <LinkBoard board={board} canEdit={canEdit} sel={sel} setSel={setSel} />
        : <Matrix board={board} onPick={(key) => { setSel({ kind: 'account', id: key }); setTab('board') }} />}

      <SubmitDialog open={submitOpen} onOpenChange={setSubmitOpen} count={stats.draft} />
    </div>
  )
}

function Stat({ label, value, hint, tone }: { label: string; value: number; hint: string; tone?: 'ok' | 'warn' | 'bad' }) {
  return (
    <div className="rounded-xl border bg-card px-4 py-3 shadow-card">
      <p className="text-sm text-muted-foreground">{label}</p>
      <p className={cn('text-2xl font-bold tabular-nums', tone === 'ok' && 'text-emerald-700 dark:text-emerald-400',
        tone === 'warn' && 'text-amber-700 dark:text-amber-400', tone === 'bad' && 'text-rose-700 dark:text-rose-400')}>{value}</p>
      <p className="text-xs text-muted-foreground">{hint}</p>
    </div>
  )
}

// ── 연결 보드 ─────────────────────────────────────────────
function LinkBoard({ board, canEdit, sel, setSel }: { board: Board; canEdit: boolean; sel: Sel; setSel: (s: Sel) => void }) {
  const add = useAddLink()
  const remove = useRemoveLink()
  const [cq, setCq] = useState('')
  const [aq, setAq] = useState('')
  const [sigOnly, setSigOnly] = useState(true)
  const [dragOver, setDragOver] = useState<string | null>(null)
  const { byControl, byAccount } = useMemo(() => indexLinks(board.links), [board.links])
  const groups = useMemo(() => groupControls(board.controls), [board.controls])
  const accts = visibleAccounts(board.accounts, { sigOnly, query: aq })
  const ctlQ = cq.trim().toLowerCase()
  const busy = add.isPending || remove.isPending

  const link = useCallback((controlId: string, accountKey: string) => {
    if (!canEdit) return
    const existing = (byControl.get(controlId) ?? []).find((l) => l.account_key === accountKey)
    if (existing && (existing.state === 'review' || existing.remove_state === 'review')) {
      toast.info('결재 중인 연결은 바꿀 수 없습니다')
      return
    }
    if (existing && !existing.remove_state) {
      remove.mutate(existing.id, { onError: (e) => toast.error(errDetail(e, '해제하지 못했습니다')) })
    } else {
      add.mutate({ control_id: controlId, account_key: accountKey }, { onError: (e) => toast.error(errDetail(e, '연결하지 못했습니다')) })
    }
  }, [add, remove, byControl, canEdit])

  const selLinks: BoardLink[] = sel ? (sel.kind === 'control' ? byControl.get(sel.id) : byAccount.get(sel.id)) ?? [] : []
  const linkedTo = new Map(selLinks.map((l) => [sel?.kind === 'control' ? l.account_key : l.control_id, l]))

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted-foreground">
        {(Object.keys(LOOK_STROKE) as LinkLook[]).map((k) => (
          <span key={k} className="inline-flex items-center gap-1.5">
            <svg width="26" height="6"><line x1="0" y1="3" x2="26" y2="3" stroke={LOOK_STROKE[k].color} strokeWidth="2.5" strokeDasharray={LOOK_STROKE[k].dash} /></svg>
            {LOOK_STROKE[k].label}
          </span>
        ))}
        <span>· 통제나 계정을 누르면 그 연결선만 보입니다{canEdit ? ' · 통제를 고른 뒤 계정을 누르면 연결/해제' : ''}</span>
      </div>
      <Lines sel={sel} links={selLinks}>
        {/* 왼쪽: 통제 */}
        <section className="flex min-w-0 flex-col rounded-xl border bg-card shadow-card">
          <header className="flex items-center gap-2 border-b px-3 py-2">
            <span className="font-semibold">RCM 통제</span>
            <span className="text-sm text-muted-foreground">{board.controls.length}</span>
            <div className="relative ml-auto w-44">
              <Search className="absolute left-2 top-2.5 h-3.5 w-3.5 text-muted-foreground" />
              <Input value={cq} onChange={(e) => setCq(e.target.value)} placeholder="코드·이름" className="h-8 pl-7 text-sm" />
            </div>
          </header>
          <div data-scroll="left" className="max-h-[70vh] min-h-[320px] overflow-y-auto p-2">
            {groups.map((g) => {
              const items = g.controls.filter((c) => !ctlQ || `${c.code} ${c.name}`.toLowerCase().includes(ctlQ))
              if (!items.length) return null
              return (
                <div key={g.code} className="mb-2">
                  <p className="sticky top-0 z-10 bg-card/95 px-1 py-1 text-xs font-semibold text-muted-foreground backdrop-blur">{g.code} · {g.name}</p>
                  {items.map((c) => {
                    const ls = byControl.get(c.id) ?? []
                    const active = ls.filter((l) => l.state === 'active' && !l.remove_state).length
                    const pending = ls.filter((l) => l.state !== 'active' || l.remove_state).length
                    const isSel = sel?.kind === 'control' && sel.id === c.id
                    const linkLk = sel?.kind === 'account' ? linkedTo.get(c.id) : undefined
                    return (
                      <div key={c.id} data-ctl={c.id}
                        draggable={canEdit}
                        onDragStart={(e) => { e.dataTransfer.setData('application/x-control', c.id); e.dataTransfer.effectAllowed = 'link' }}
                        onDragOver={(e) => { if (e.dataTransfer.types.includes('application/x-account')) { e.preventDefault(); setDragOver(`c:${c.id}`) } }}
                        onDragLeave={() => setDragOver(null)}
                        onDrop={(e) => { const k = e.dataTransfer.getData('application/x-account'); setDragOver(null); if (k) link(c.id, k) }}
                        onClick={() => {
                          if (sel?.kind === 'account' && canEdit) link(c.id, sel.id)
                          else setSel(isSel ? null : { kind: 'control', id: c.id })
                        }}
                        className={cn('group mb-1 cursor-pointer rounded-lg border px-2.5 py-1.5 text-sm transition-colors',
                          canEdit && 'active:cursor-grabbing',
                          isSel ? 'border-primary bg-accent ring-2 ring-primary/30' : 'hover:bg-muted/60',
                          linkLk && LOOK_CHIP[linkLook(linkLk)],
                          dragOver === `c:${c.id}` && 'ring-2 ring-primary')}>
                        <div className="flex items-center gap-1.5">
                          <span className="font-mono text-xs text-muted-foreground">{c.code}</span>
                          {c.is_key_control && <Star className="h-3 w-3 fill-amber-400 text-amber-500" aria-label="핵심통제" />}
                          <span className="ml-auto text-xs tabular-nums text-muted-foreground">
                            {active > 0 && <span className="font-semibold text-primary">{active}</span>}
                            {pending > 0 && <span className="text-amber-600"> +{pending}</span>}
                            {active + pending === 0 && <span>—</span>}
                          </span>
                        </div>
                        <p className="line-clamp-2 leading-snug">{c.name}</p>
                        {isSel && c.related_accounts && (
                          <p className="mt-1 text-xs text-muted-foreground">RCM 관련 계정: {c.related_accounts}</p>
                        )}
                      </div>
                    )
                  })}
                </div>
              )
            })}
          </div>
        </section>

        <div aria-hidden className="hidden lg:block" />

        {/* 오른쪽: 계정 */}
        <section className="flex min-w-0 flex-col rounded-xl border bg-card shadow-card">
          <header className="flex flex-wrap items-center gap-2 border-b px-3 py-2">
            <span className="font-semibold">계정</span>
            <span className="text-sm text-muted-foreground">{accts.length}</span>
            <label className="flex items-center gap-1.5 text-sm">
              <Checkbox checked={sigOnly} onCheckedChange={(v) => setSigOnly(v === true)} />유의 계정만
            </label>
            <div className="relative ml-auto w-44">
              <Search className="absolute left-2 top-2.5 h-3.5 w-3.5 text-muted-foreground" />
              <Input value={aq} onChange={(e) => setAq(e.target.value)} placeholder="계정명" className="h-8 pl-7 text-sm" />
            </div>
          </header>
          <div data-scroll="right" className="max-h-[70vh] min-h-[320px] overflow-y-auto p-2">
            {accts.length === 0 && <p className="p-6 text-center text-sm text-muted-foreground">조건에 맞는 계정이 없습니다</p>}
            {accts.map((a) => {
              const ls = byAccount.get(a.key) ?? []
              const cov = accountCoverage(ls)
              const isSel = sel?.kind === 'account' && sel.id === a.key
              const linkLk = sel?.kind === 'control' ? linkedTo.get(a.key) : undefined
              const parent = sigOnly || aq ? parentName(board.accounts, a) : null
              return (
                <div key={a.key} data-acc={a.key}
                  draggable={canEdit}
                  onDragStart={(e) => { e.dataTransfer.setData('application/x-account', a.key); e.dataTransfer.effectAllowed = 'link' }}
                  onDragOver={(e) => { if (e.dataTransfer.types.includes('application/x-control')) { e.preventDefault(); setDragOver(`a:${a.key}`) } }}
                  onDragLeave={() => setDragOver(null)}
                  onDrop={(e) => { const c = e.dataTransfer.getData('application/x-control'); setDragOver(null); if (c) link(c, a.key) }}
                  onClick={() => {
                    if (sel?.kind === 'control' && canEdit) link(sel.id, a.key)
                    else setSel(isSel ? null : { kind: 'account', id: a.key })
                  }}
                  style={{ paddingLeft: sigOnly || aq ? undefined : 10 + a.depth * 14 }}
                  className={cn('mb-1 flex cursor-pointer items-center gap-2 rounded-lg border px-2.5 py-1.5 text-sm transition-colors',
                    isSel ? 'border-primary bg-accent ring-2 ring-primary/30' : 'hover:bg-muted/60',
                    linkLk && LOOK_CHIP[linkLook(linkLk)],
                    dragOver === `a:${a.key}` && 'ring-2 ring-primary',
                    busy && 'opacity-80')}>
                  <Badge variant="outline" className="shrink-0 px-1.5 text-[10px]">{a.statement_type}</Badge>
                  <div className="min-w-0 flex-1">
                    <p className={cn('truncate', a.has_children && 'font-semibold')}>{a.name}</p>
                    {parent && <p className="truncate text-xs text-muted-foreground">{parent}</p>}
                  </div>
                  {a.significant === 'Y' && <span className="rounded border border-rose-200 bg-rose-50 px-1 text-[11px] font-semibold text-rose-700 dark:border-rose-800 dark:bg-rose-950/40 dark:text-rose-300">유의</span>}
                  <span className={cn('h-2.5 w-2.5 shrink-0 rounded-full',
                    cov === 'covered' ? 'bg-primary' : cov === 'pending' ? 'bg-amber-500' : a.significant === 'Y' ? 'bg-rose-500' : 'bg-muted-foreground/30')}
                    title={cov === 'covered' ? '확정된 통제 있음' : cov === 'pending' ? '작성·결재 중인 연결만 있음' : '연결된 통제 없음'} />
                  {linkLk && <span className="shrink-0 text-[11px]">{MATCH_LABEL[linkLk.match_kind ?? ''] ?? ''}</span>}
                </div>
              )
            })}
          </div>
        </section>
      </Lines>
    </div>
  )
}

/**
 * 초점 연결선 — 고른 통제(또는 계정)의 연결만 SVG 곡선으로 그린다. 전부 그리면 실타래가 된다.
 * 두 목록이 각자 스크롤되므로 스크롤·크기 변경마다 다시 잰다. 화면 밖 항목은 목록 가장자리에 붙여 방향만 보인다.
 */
function Lines({ sel, links, children }: { sel: Sel; links: BoardLink[]; children: React.ReactNode }) {
  const ref = useRef<HTMLDivElement>(null)
  const [paths, setPaths] = useState<{ d: string; look: LinkLook; key: string }[]>([])
  const measure = useCallback(() => {
    const root = ref.current
    if (!root || !sel) { setPaths([]); return }
    const box = root.getBoundingClientRect()
    const left = root.querySelector<HTMLElement>('[data-scroll="left"]')?.getBoundingClientRect()
    const right = root.querySelector<HTMLElement>('[data-scroll="right"]')?.getBoundingClientRect()
    if (!left || !right) return
    const clampY = (y: number, r: DOMRect) => Math.min(Math.max(y, r.top + 6), r.bottom - 6)
    const out: { d: string; look: LinkLook; key: string }[] = []
    for (const l of links) {
      const c = root.querySelector<HTMLElement>(`[data-ctl="${CSS.escape(l.control_id)}"]`)?.getBoundingClientRect()
      const a = root.querySelector<HTMLElement>(`[data-acc="${CSS.escape(l.account_key)}"]`)?.getBoundingClientRect()
      if (!c || !a) continue
      const x1 = c.right - box.left, y1 = clampY(c.top + c.height / 2, left) - box.top
      const x2 = a.left - box.left, y2 = clampY(a.top + a.height / 2, right) - box.top
      const mx = (x1 + x2) / 2
      out.push({ d: `M${x1},${y1} C${mx},${y1} ${mx},${y2} ${x2},${y2}`, look: linkLook(l), key: l.id })
    }
    setPaths(out)
  }, [sel, links])

  useLayoutEffect(() => { measure() }, [measure])
  useEffect(() => {
    const root = ref.current
    if (!root) return
    const lists = root.querySelectorAll('[data-scroll]')
    lists.forEach((el) => el.addEventListener('scroll', measure, { passive: true }))
    window.addEventListener('resize', measure)
    return () => {
      lists.forEach((el) => el.removeEventListener('scroll', measure))
      window.removeEventListener('resize', measure)
    }
  }, [measure])

  return (
    <div ref={ref} className="relative grid gap-3 lg:grid-cols-[minmax(0,1fr)_72px_minmax(0,1.25fr)] lg:gap-0">
      {children}
      <svg className="pointer-events-none absolute inset-0 hidden h-full w-full lg:block" aria-hidden>
        {paths.map((p) => (
          <g key={p.key}>
            <path d={p.d} fill="none" stroke={LOOK_STROKE[p.look].color} strokeWidth={2.25} strokeDasharray={LOOK_STROKE[p.look].dash} />
          </g>
        ))}
      </svg>
    </div>
  )
}

// ── 매트릭스 ─────────────────────────────────────────────
function Matrix({ board, onPick }: { board: Board; onPick: (key: string) => void }) {
  const m = useMemo(() => buildMatrix(board), [board])
  const [gapOnly, setGapOnly] = useState(false)
  const rows = gapOnly ? m.rows.filter((r) => r.active === 0) : m.rows
  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-3 text-sm text-muted-foreground">
        <span>행 = 유의 계정 · 열 = 프로세스 · 칸 = 확정 통제 수(<span className="text-amber-600">+작성·결재 중</span>). 행을 누르면 보드에서 엽니다.</span>
        <label className="ml-auto flex items-center gap-1.5"><Checkbox checked={gapOnly} onCheckedChange={(v) => setGapOnly(v === true)} />확정 통제 없는 계정만</label>
      </div>
      <div className="max-h-[72vh] overflow-auto rounded-xl border bg-card shadow-card">
        <table className="w-full border-collapse text-sm">
          <thead className="sticky top-0 z-10 bg-card">
            <tr className="border-b">
              <th className="sticky left-0 z-20 min-w-[200px] bg-card px-3 py-2 text-left font-semibold">계정</th>
              {m.processes.map((p) => (
                <th key={p.code} className="min-w-[72px] px-2 py-2 text-center text-xs font-medium text-muted-foreground" title={p.name}>
                  <div className="font-mono">{p.code}</div><div className="truncate">{p.name}</div>
                </th>
              ))}
              <th className="px-3 py-2 text-center font-semibold">합계</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.account.key} onClick={() => onPick(r.account.key)}
                className={cn('cursor-pointer border-b hover:bg-muted/50', r.active === 0 && 'bg-rose-50/60 dark:bg-rose-950/20')}>
                <td className="sticky left-0 bg-inherit px-3 py-1.5">
                  <span className="mr-1.5 text-[10px] text-muted-foreground">{r.account.statement_type}</span>{r.account.name}
                </td>
                {m.processes.map((p) => {
                  const c = r.cells[p.code]
                  return (
                    <td key={p.code} className="px-2 py-1.5 text-center tabular-nums">
                      {c ? (<>
                        {c.active > 0 && <span className="inline-flex h-6 min-w-6 items-center justify-center rounded bg-primary px-1 text-xs font-semibold text-primary-foreground">{c.active}</span>}
                        {c.pending > 0 && <span className="ml-0.5 text-xs text-amber-600">+{c.pending}</span>}
                      </>) : <span className="text-muted-foreground/40">·</span>}
                    </td>
                  )
                })}
                <td className={cn('px-3 py-1.5 text-center font-semibold tabular-nums', r.active === 0 && 'text-rose-700 dark:text-rose-300')}>
                  {r.active}{r.pending > 0 && <span className="text-xs font-normal text-amber-600"> +{r.pending}</span>}
                </td>
              </tr>
            ))}
            {rows.length === 0 && (
              <tr><td colSpan={m.processes.length + 2} className="p-8 text-center text-muted-foreground">
                {m.rows.length ? '모든 유의 계정에 확정 통제가 있습니다' : '유의 계정이 없습니다 — 스코핑을 먼저 평가하세요'}
              </td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function SubmitDialog({ open, onOpenChange, count }: { open: boolean; onOpenChange: (o: boolean) => void; count: number }) {
  const [note, setNote] = useState('')
  const submit = useSubmitLinks()
  const nav = useNavigate()
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>연결 검토 요청</DialogTitle>
          <DialogDescription>
            작성 중인 변경 {count}건(연결 추가·해제)을 한 묶음으로 올립니다. 책임관리자가 항목별로 1차 승인하고 마스터관리자가 2차 승인하면 확정됩니다.
            요청한 본인은 승인할 수 없습니다.
          </DialogDescription>
        </DialogHeader>
        <Textarea rows={3} value={note} onChange={(e) => setNote(e.target.value)} placeholder="요청 메모(선택) — 예: 매출·결산 프로세스 연결 정리" />
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>취소</Button>
          <Button disabled={submit.isPending} onClick={() => submit.mutate(note, {
            onSuccess: (r) => { toast.success('검토를 요청했습니다'); onOpenChange(false); setNote(''); nav(`/proposals/${r.proposal_id}`) },
            onError: (e) => toast.error(errDetail(e, '요청하지 못했습니다')),
          })}>요청</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
