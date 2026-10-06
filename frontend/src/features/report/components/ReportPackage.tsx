import { useMemo, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import {
  AlertTriangle, CheckCircle2, FileText, Lock, Pencil, Plus, Printer, RotateCcw, Settings2, Trash2, Unlock,
} from 'lucide-react'
import apiClient from '@/lib/axios'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { useActiveTenantId, useAuthStore } from '@/features/auth/store'
import { isIcfrManagerForUser, isIcfrStaffForUser } from '@/features/auth/permissions.pure'
import type { ReportFacts } from '../reportModel'
import { useOfficerNames } from '@/features/admin/components/OfficerRoles'
import { useFiscal } from '@/lib/useFiscal'
import {
  DOCS, META_FIELDS, META_ROWS, metaRows, placeholders, rowsOf, sectionText, timeline,
  type Block, type Contents, type Ctx, type DocContent, type DocDef, type DocKey,
} from '../reportTemplates'

interface YearRow { fiscal_year: number; documents: number; final: number; updated_at: string | null }

interface DocRow {
  doc_key: DocKey
  content: DocContent
  status: 'draft' | 'final'
  version: number
  updated_at: string | null
  updated_by: string | null
  finalized_at: string | null
  finalized_by: string | null
}

const errText = (e: unknown, f: string) => (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? f

// 문서 스타일 — 화면과 인쇄 창이 같은 CSS(.icfr-pkg 하위)
export const PKG_CSS = `
.icfr-pkg { background:#fff; color:#111; font-family:'Malgun Gothic','Apple SD Gothic Neo',sans-serif; line-height:1.75; font-size:13.5px; overflow-wrap:anywhere; }
.icfr-pkg .doc { max-width:760px; margin:0 auto; }
.icfr-pkg h2 { font-size:20px; font-weight:700; text-align:center; margin:4px 0 18px; letter-spacing:.02em; }
.icfr-pkg .addressee { font-weight:600; margin:0 0 14px; }
.icfr-pkg h3 { font-size:14.5px; font-weight:700; margin:18px 0 6px; }
.icfr-pkg p.para { margin:0 0 10px; text-align:justify; white-space:pre-line; }
.icfr-pkg table { border-collapse:collapse; width:100%; margin:4px 0 12px; }
.icfr-pkg th, .icfr-pkg td { border:1px solid #9ca3af; padding:5px 9px; text-align:left; vertical-align:top; white-space:pre-line; }
.icfr-pkg th { background:#f3f4f6; font-weight:600; }
.icfr-pkg .date { text-align:center; margin:28px 0 12px; }
.icfr-pkg .signers { text-align:right; line-height:2.2; }
.icfr-pkg .hint { color:#6b7280; font-size:12px; margin-top:16px; }
.icfr-pkg .ph { background:#fef3c7; }
`
const PRINT_CSS = `@page { size:A4; margin:20mm 18mm; } body{margin:0} .icfr-pkg .doc + .doc { break-before: page; } .icfr-pkg table, .icfr-pkg .signers { break-inside: avoid; } .icfr-pkg h3 { break-after: avoid; } .icfr-pkg .ph { background:none; }`

function printHtml(title: string, html: string) {
  const w = window.open('', '_blank', 'width=900,height=1000')
  if (!w) { toast.error('팝업이 막혀 있습니다 — 이 사이트의 팝업을 허용하세요'); return }
  w.document.write(`<!doctype html><html lang="ko"><head><meta charset="utf-8"><title>${title.replace(/[<>&]/g, '')}</title><style>${PKG_CSS}${PRINT_CSS}</style></head><body><div class="icfr-pkg">${html}</div></body></html>`)
  w.document.close()
  w.focus()
  w.print()
}

/** 자리표시 `(회사명)` 같은 미입력 칸을 노랗게 — 인쇄 시엔 표시 안 함 */
function Hl({ text }: { text: string }) {
  const parts = text.split(/(\([^()\n]{1,20}\))/g)
  return <>{parts.map((p, i) => (/^\([^()\n]{1,20}\)$/.test(p) && placeholders(p).length ? <span key={i} className="ph">{p}</span> : p))}</>
}

/**
 * 이사회 보고 패키지(2026-10-06) — 회계연도별 법정 보고서 2종 + 이사회 보고 자료 2종 + 의사록(안) 2종.
 * 기본 문구는 평가 데이터와 기본 정보로 만들고, 고친 문단·표만 저장한다(`/api/report/documents/{연도}`).
 */
export default function ReportPackage({ facts }: { facts: ReportFacts }) {
  const tid = useActiveTenantId()
  const user = useAuthStore((s) => s.user)
  const canEdit = isIcfrStaffForUser(user) && Boolean(user?.can_write)
  const isMaster = isIcfrManagerForUser(user)
  const thisYear = new Date().getFullYear()
  const [fy, setFy] = useState<number>(() => (facts.fiscalYear && facts.fiscalYear < thisYear ? facts.fiscalYear : thisYear - 1))
  const [active, setActive] = useState<DocKey>('meta')
  const qc = useQueryClient()
  const { data: rows = [], isLoading } = useQuery({
    queryKey: ['report-docs', tid, fy],
    queryFn: async () => (await apiClient.get<DocRow[]>(`/api/report/documents/${fy}`)).data,
  })
  const byKey = useMemo(() => Object.fromEntries(rows.map((r) => [r.doc_key, r])) as Partial<Record<DocKey, DocRow>>, [rows])
  const contents: Contents = useMemo(() => Object.fromEntries(rows.map((r) => [r.doc_key, r.content])), [rows])
  const officers = useOfficerNames()
  const fiscal = useFiscal()
  const ctx: Ctx = { fy, facts, contents, startMonth: fiscal.startMonth,
    defaults: { ceo: officers.ceo ?? '', icfr_manager: officers.icfr_manager ?? '' } }
  const { data: years = [] } = useQuery({
    queryKey: ['report-years', tid],
    queryFn: async () => (await apiClient.get<YearRow[]>('/api/report/years')).data,
  })
  // 평가 대상 연도 — 작성한 연도 + 최근 연도(올해·작년)를 합쳐 최신순
  const yearList = [...new Set([thisYear, thisYear - 1, ...years.map((y) => y.fiscal_year), fy])].sort((a, b) => b - a)
  const yearInfo = new Map(years.map((y) => [y.fiscal_year, y]))

  const save = useMutation({
    mutationFn: async ({ key, content }: { key: DocKey; content: DocContent }) =>
      (await apiClient.put<DocRow>(`/api/report/documents/${fy}/${key}`, { content })).data,
    onSuccess: () => { void qc.invalidateQueries({ queryKey: ['report-docs', tid, fy] }); void qc.invalidateQueries({ queryKey: ['report-years', tid] }) },
    onError: (e) => toast.error(errText(e, '저장하지 못했습니다')),
  })
  const act = useMutation({
    mutationFn: async ({ key, op, reason }: { key: DocKey; op: 'finalize' | 'reopen'; reason?: string }) =>
      (await apiClient.post<DocRow>(`/api/report/documents/${fy}/${key}/${op}`, { reason: reason ?? null })).data,
    onSuccess: (_d, v) => { toast.success(v.op === 'finalize' ? '확정했습니다' : '재오픈했습니다'); void qc.invalidateQueries({ queryKey: ['report-docs', tid, fy] }) },
    onError: (e) => toast.error(errText(e, '처리하지 못했습니다')),
  })

  const docRef = useRef<HTMLDivElement>(null)
  const allRef = useRef<HTMLDivElement>(null)
  const doc = DOCS.find((d) => d.key === active)
  const row = byKey[active]
  const locked = row?.status === 'final'
  const editable = canEdit && !locked

  const writeDoc = (key: DocKey, patch: (c: DocContent) => DocContent) =>
    save.mutate({ key, content: patch(structuredClone(contents[key] ?? {})) })

  return (
    <div className="space-y-4">
      <style>{PKG_CSS}</style>
      {/* 보고 순서 */}
      <div className="flex flex-wrap items-center gap-3 rounded-xl border bg-card p-4 shadow-card">
        <div className="w-full space-y-1.5">
          <p className="text-sm font-medium">평가 대상 회계연도 <span className="font-normal text-muted-foreground">— 회계연도마다 보고 패키지가 따로 있습니다 · {fiscal.endMonth}월 결산</span></p>
          <div className="flex flex-wrap gap-2" role="tablist" aria-label="평가 대상 연도">
            {yearList.map((y) => {
              const info = yearInfo.get(y)
              return (
                <button key={y} type="button" role="tab" aria-selected={fy === y} onClick={() => { setFy(y); setActive('meta') }}
                  className={cn('rounded-lg border px-3 py-1.5 text-left text-sm transition-colors',
                    fy === y ? 'border-primary bg-primary text-primary-foreground' : 'hover:bg-muted')}>
                  <span className="font-semibold">{y} 회계연도</span>
                  <span className={cn('ml-1.5 text-xs', fy === y ? 'text-primary-foreground/80' : 'text-muted-foreground')}>{fiscal.rangeText(y)}</span>
                  <span className={cn('ml-2 text-xs', fy === y ? 'text-primary-foreground/80' : 'text-muted-foreground')}>
                    {info ? `작성 ${info.documents}/${DOCS.length} · 확정 ${info.final}` : '미작성'}
                  </span>
                </button>
              )
            })}
          </div>
        </div>
        <ol className="flex flex-1 flex-wrap items-stretch gap-2">
          {timeline(ctx).map((t, i) => (
            <li key={t.step} className="min-w-[180px] flex-1 rounded-lg border bg-muted/40 px-3 py-2 text-xs">
              <p className="text-sm font-semibold">{i + 1}. {t.step} <span className="font-normal text-muted-foreground">{t.date || '일자 미정'}</span></p>
              <ul className="mt-1 list-disc pl-4 text-muted-foreground">{t.items.map((x) => <li key={x}>{x}</li>)}</ul>
            </li>
          ))}
        </ol>
        <Button variant="outline" onClick={() => allRef.current && printHtml(`${fy} 이사회 보고 패키지`, allRef.current.innerHTML)}>
          <Printer className="mr-1.5 h-4 w-4" />패키지 전체 인쇄
        </Button>
      </div>

      <div className="grid gap-4 lg:grid-cols-[260px_minmax(0,1fr)]">
        <nav className="space-y-1">
          <NavItem active={active === 'meta'} onClick={() => setActive('meta')} icon={<Settings2 className="h-4 w-4" />}
            title="기본 정보" sub="회사·서명자·회의 일정·위원 명단" status={byKey.meta?.status} />
          {DOCS.map((d) => (
            <NavItem key={d.key} active={active === d.key} onClick={() => setActive(d.key)} icon={<FileText className="h-4 w-4" />}
              title={d.short} sub={d.statutory ? '법정 보고서' : d.companyForm ? '회사 양식(안)' : '이사회 보고 자료'}
              status={byKey[d.key]?.status} edited={hasEdits(contents[d.key])} />
          ))}
          <p className="px-2 pt-2 text-xs text-muted-foreground">별첨: 평가 결과 데이터(실무 양식)는 위쪽 ‘별첨’ 탭에 있습니다.</p>
        </nav>

        <section className="min-w-0 rounded-xl border bg-card shadow-card">
          <header className="flex flex-wrap items-center gap-2 border-b px-4 py-3">
            <h2 className="text-base font-semibold">{active === 'meta' ? '기본 정보' : doc?.title}</h2>
            {active !== 'meta' && doc && <span className="text-xs text-muted-foreground">{doc.audience}</span>}
            {locked && <Badge className="gap-1"><Lock className="h-3 w-3" />확정 {row?.finalized_by ? `· ${row.finalized_by}` : ''}</Badge>}
            {row?.updated_by && !locked && <span className="text-xs text-muted-foreground">마지막 수정 {row.updated_by}</span>}
            <span className="ml-auto flex gap-2">
              {active !== 'meta' && (
                <Button size="sm" variant="outline" onClick={() => docRef.current && printHtml(doc?.title ?? '', docRef.current.innerHTML)}>
                  <Printer className="mr-1.5 h-4 w-4" />인쇄
                </Button>
              )}
              {isMaster && !locked && (
                <Button size="sm" disabled={act.isPending} onClick={() => {
                  const n = active === 'meta' ? 0 : countPlaceholders(doc!, ctx)
                  if (n && !window.confirm(`채우지 않은 칸이 ${n}개 있습니다. 그래도 확정할까요?`)) return
                  act.mutate({ key: active, op: 'finalize' })
                }}><CheckCircle2 className="mr-1.5 h-4 w-4" />확정</Button>
              )}
              {isMaster && locked && (
                <Button size="sm" variant="outline" disabled={act.isPending} onClick={() => {
                  const r = window.prompt('재오픈 사유')
                  if (r?.trim()) act.mutate({ key: active, op: 'reopen', reason: r.trim() })
                }}><Unlock className="mr-1.5 h-4 w-4" />재오픈</Button>
              )}
            </span>
          </header>
          <div className="p-4 sm:p-6">
            {isLoading ? <p className="text-sm text-muted-foreground">불러오는 중…</p>
              : active === 'meta'
                ? <MetaForm content={contents.meta ?? {}} editable={editable} saving={save.isPending}
                    onSave={(c) => save.mutate({ key: 'meta', content: c }, { onSuccess: () => toast.success('기본 정보를 저장했습니다') })} />
                : doc && (
                  <>
                    {doc.companyForm && (
                      <p className="mb-3 rounded-md bg-muted px-3 py-2 text-xs text-muted-foreground">
                        의사록 양식은 회사마다 다릅니다. 이 문서는 우리 회사 사례를 바탕으로 한 <b>초안</b>이며, 문단을 눌러 회사 양식에 맞게 고치세요.
                      </p>
                    )}
                    <PlaceholderBanner n={countPlaceholders(doc, ctx)} />
                    <div className="icfr-pkg"><div ref={docRef}>
                      <DocBody doc={doc} ctx={ctx} editable={editable} onWrite={(patch) => writeDoc(doc.key, patch)} />
                    </div></div>
                  </>
                )}
          </div>
        </section>
      </div>

      {/* 패키지 전체 인쇄용 — 화면에 보이지 않는다 */}
      <div className="hidden">
        <div ref={allRef}>
          {DOCS.map((d) => <DocBody key={d.key} doc={d} ctx={ctx} editable={false} onWrite={() => {}} />)}
        </div>
      </div>
    </div>
  )
}

const hasEdits = (c?: DocContent) => Boolean(c && (Object.keys(c.sections ?? {}).length || Object.keys(c.rows ?? {}).length))

function countPlaceholders(doc: DocDef, ctx: Ctx): number {
  let n = 0
  for (const b of doc.blocks(ctx)) {
    if (b.kind === 'para') n += placeholders(sectionText(ctx, doc.key, b.key, b.text).text).length
    else if (b.kind === 'title' || b.kind === 'addressee' || b.kind === 'heading') n += placeholders(b.text).length
    else if (b.kind === 'date') n += placeholders(b.text(ctx)).length
    else if (b.kind === 'signers') n += b.lines(ctx).reduce((s, l) => s + placeholders(l).length, 0)
  }
  return n
}

function PlaceholderBanner({ n }: { n: number }) {
  if (!n) return null
  return (
    <p className="mb-3 flex items-center gap-1.5 rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-xs text-amber-900 dark:border-amber-700 dark:bg-amber-950/40 dark:text-amber-200">
      <AlertTriangle className="h-3.5 w-3.5" />노란 칸 {n}개가 아직 비어 있습니다 — 기본 정보를 채우거나 문단을 눌러 고치세요.
    </p>
  )
}

function NavItem({ active, onClick, icon, title, sub, status, edited }: {
  active: boolean; onClick: () => void; icon: React.ReactNode; title: string; sub: string; status?: string; edited?: boolean
}) {
  return (
    <button type="button" onClick={onClick}
      className={cn('flex w-full items-start gap-2 rounded-lg border px-3 py-2 text-left transition-colors',
        active ? 'border-primary bg-accent' : 'border-transparent hover:bg-muted')}>
      <span className="mt-0.5 text-muted-foreground">{icon}</span>
      <span className="min-w-0 flex-1">
        <span className="block text-sm font-medium">{title}</span>
        <span className="block text-xs text-muted-foreground">{sub}</span>
      </span>
      {status === 'final' ? <Badge className="shrink-0 px-1.5 text-[10px]">확정</Badge>
        : edited ? <Badge variant="outline" className="shrink-0 px-1.5 text-[10px]">수정됨</Badge> : null}
    </button>
  )
}

// ── 문서 본문 ─────────────────────────────────────────────
function DocBody({ doc, ctx, editable, onWrite }: {
  doc: DocDef; ctx: Ctx; editable: boolean; onWrite: (patch: (c: DocContent) => DocContent) => void
}) {
  return (
    <div className="doc">
      {doc.blocks(ctx).map((b, i) => <BlockView key={`${doc.key}-${i}`} b={b} doc={doc} ctx={ctx} editable={editable} onWrite={onWrite} />)}
    </div>
  )
}

function BlockView({ b, doc, ctx, editable, onWrite }: {
  b: Block; doc: DocDef; ctx: Ctx; editable: boolean; onWrite: (patch: (c: DocContent) => DocContent) => void
}) {
  switch (b.kind) {
    case 'title': return <h2><Hl text={b.text} /></h2>
    case 'addressee': return <p className="addressee"><Hl text={b.text} /></p>
    case 'heading': return <h3>{b.text}</h3>
    case 'date': return <p className="date"><Hl text={b.text(ctx)} /></p>
    case 'signers': return <div className="signers">{b.lines(ctx).map((l, i) => <div key={i}><Hl text={l} /></div>)}</div>
    case 'hint': return <p className="hint">{b.text}</p>
    case 'para': return <ParaBlock b={b} doc={doc} ctx={ctx} editable={editable} onWrite={onWrite} />
    case 'rows': return <RowsBlock b={b} doc={doc} ctx={ctx} editable={editable} onWrite={onWrite} />
  }
}

function ParaBlock({ b, doc, ctx, editable, onWrite }: {
  b: Extract<Block, { kind: 'para' }>; doc: DocDef; ctx: Ctx; editable: boolean; onWrite: (patch: (c: DocContent) => DocContent) => void
}) {
  const { text, edited } = sectionText(ctx, doc.key, b.key, b.text)
  const [draft, setDraft] = useState<string | null>(null)
  if (draft !== null) {
    return (
      <div className="my-2 space-y-2 rounded-lg border border-primary/40 bg-accent/40 p-3 font-sans">
        <p className="text-xs font-medium text-muted-foreground">{b.label}{b.note ? ` — ${b.note}` : ''}</p>
        <Textarea rows={Math.min(14, Math.max(4, Math.ceil(draft.length / 60)))} value={draft} onChange={(e) => setDraft(e.target.value)} className="bg-background text-[13.5px] leading-relaxed" />
        <div className="flex flex-wrap gap-2">
          <Button size="sm" onClick={() => { onWrite((c) => ({ ...c, sections: { ...c.sections, [b.key]: draft } })); setDraft(null) }}>저장</Button>
          <Button size="sm" variant="ghost" onClick={() => setDraft(null)}>취소</Button>
          {edited && (
            <Button size="sm" variant="ghost" className="ml-auto" onClick={() => {
              onWrite((c) => { const s = { ...c.sections }; delete s[b.key]; return { ...c, sections: s } })
              setDraft(null)
            }}><RotateCcw className="mr-1 h-3.5 w-3.5" />기본 문구로</Button>
          )}
        </div>
      </div>
    )
  }
  return (
    <div className={cn('group relative', editable && 'cursor-text rounded-md hover:bg-amber-50/60 hover:outline hover:outline-1 hover:outline-amber-300 dark:hover:bg-amber-950/20')}
      onClick={() => editable && setDraft(text)} title={editable ? `${b.label} — 눌러서 고치기` : undefined}>
      <p className="para"><Hl text={text} /></p>
      {editable && (
        <span className="pointer-events-none absolute -right-1 -top-2 hidden items-center gap-1 rounded bg-background px-1 text-[10px] text-muted-foreground shadow group-hover:flex print:hidden">
          <Pencil className="h-3 w-3" />{edited ? '수정됨' : b.label}
        </span>
      )}
    </div>
  )
}

function RowsBlock({ b, doc, ctx, editable, onWrite }: {
  b: Extract<Block, { kind: 'rows' }>; doc: DocDef; ctx: Ctx; editable: boolean; onWrite: (patch: (c: DocContent) => DocContent) => void
}) {
  const defaults = b.defaults(ctx)
  const rows = rowsOf(ctx, doc.key, b.key, defaults)
  const edited = ctx.contents[doc.key]?.rows?.[b.key] != null
  const [draft, setDraft] = useState<string[][] | null>(null)
  if (draft) {
    return (
      <div className="my-2 space-y-2 rounded-lg border border-primary/40 bg-accent/40 p-3 font-sans">
        <p className="text-xs font-medium text-muted-foreground">{b.label}</p>
        <RowEditor cols={b.cols} rows={draft} onChange={setDraft} />
        <div className="flex flex-wrap gap-2">
          <Button size="sm" onClick={() => { onWrite((c) => ({ ...c, rows: { ...c.rows, [b.key]: draft } })); setDraft(null) }}>저장</Button>
          <Button size="sm" variant="ghost" onClick={() => setDraft(null)}>취소</Button>
          {edited && (
            <Button size="sm" variant="ghost" className="ml-auto" onClick={() => {
              onWrite((c) => { const r = { ...c.rows }; delete r[b.key]; return { ...c, rows: r } })
              setDraft(null)
            }}><RotateCcw className="mr-1 h-3.5 w-3.5" />기본값으로</Button>
          )}
        </div>
      </div>
    )
  }
  if (!rows.length && !editable) return null
  return (
    <div className={cn('group relative', editable && 'cursor-pointer rounded-md hover:outline hover:outline-1 hover:outline-amber-300')}
      onClick={() => editable && setDraft(rows.length ? rows.map((r) => [...r]) : [b.cols.map(() => '')])}>
      {rows.length ? (
        <table>
          <thead><tr>{b.cols.map((c) => <th key={c}>{c}</th>)}</tr></thead>
          <tbody>{rows.map((r, i) => <tr key={i}>{b.cols.map((_c, j) => <td key={j}><Hl text={r[j] ?? ''} /></td>)}</tr>)}</tbody>
        </table>
      ) : (
        <p className="hint">+ {b.label} 추가</p>
      )}
      {editable && rows.length > 0 && (
        <span className="pointer-events-none absolute -right-1 -top-2 hidden items-center gap-1 rounded bg-background px-1 text-[10px] text-muted-foreground shadow group-hover:flex">
          <Pencil className="h-3 w-3" />{edited ? '수정됨' : `${b.label} 고치기`}
        </span>
      )}
    </div>
  )
}

function RowEditor({ cols, rows, onChange }: { cols: string[]; rows: string[][]; onChange: (r: string[][]) => void }) {
  const set = (i: number, j: number, v: string) => onChange(rows.map((r, a) => (a === i ? r.map((x, b) => (b === j ? v : x)) : r)))
  return (
    <div className="space-y-1.5">
      <div className="grid gap-1.5 text-xs font-medium text-muted-foreground" style={{ gridTemplateColumns: `repeat(${cols.length}, minmax(0,1fr)) 32px` }}>
        {cols.map((c) => <span key={c}>{c}</span>)}<span />
      </div>
      {rows.map((r, i) => (
        <div key={i} className="grid gap-1.5" style={{ gridTemplateColumns: `repeat(${cols.length}, minmax(0,1fr)) 32px` }}>
          {cols.map((_c, j) => (
            <Textarea key={j} rows={1} value={r[j] ?? ''} onChange={(e) => set(i, j, e.target.value)} className="min-h-9 bg-background py-1.5 text-sm" />
          ))}
          <Button size="icon" variant="ghost" className="h-9 w-8" aria-label="행 삭제" onClick={() => onChange(rows.filter((_, a) => a !== i))}>
            <Trash2 className="h-4 w-4" />
          </Button>
        </div>
      ))}
      <Button size="sm" variant="outline" onClick={() => onChange([...rows, cols.map(() => '')])}><Plus className="mr-1 h-3.5 w-3.5" />행 추가</Button>
    </div>
  )
}

// ── 기본 정보 ─────────────────────────────────────────────
function MetaForm({ content, editable, saving, onSave }: {
  content: DocContent; editable: boolean; saving: boolean; onSave: (c: DocContent) => void
}) {
  const [fields, setFields] = useState<Record<string, string>>(() => ({ framework: 'sme', ...(content.fields ?? {}) }))
  const [rows, setRows] = useState<Record<string, string[][]>>(() => content.rows ?? {})
  const groups = [...new Set(META_FIELDS.map((f) => f.group))]
  const dirty = JSON.stringify({ f: { framework: 'sme', ...(content.fields ?? {}) }, r: content.rows ?? {} }) !== JSON.stringify({ f: fields, r: rows })
  const fake: Ctx = { fy: 0, facts: {} as ReportFacts, contents: { meta: { rows } } }
  return (
    <div className="space-y-6">
      <p className="text-sm text-muted-foreground">여기 적은 값이 모든 문서의 회사명·서명자·회의 일시·위원 명단에 들어갑니다. 비워 둔 칸은 문서에 노란 칸으로 표시됩니다.</p>
      {groups.map((g) => (
        <fieldset key={g} className="space-y-2">
          <legend className="text-sm font-semibold">{g}</legend>
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
            {META_FIELDS.filter((f) => f.group === g).map((f) => (
              <label key={f.key} className="space-y-1 text-sm">
                <span className="text-muted-foreground">{f.label}</span>
                {f.type === 'select' ? (
                  <select disabled={!editable} value={fields[f.key] ?? ''} onChange={(e) => setFields({ ...fields, [f.key]: e.target.value })}
                    className="h-10 w-full rounded-md border bg-background px-2 py-0">
                    {f.options!.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
                  </select>
                ) : (
                  <Input disabled={!editable} type={f.type === 'date' ? 'date' : 'text'} value={fields[f.key] ?? ''} placeholder={f.hint}
                    onChange={(e) => setFields({ ...fields, [f.key]: e.target.value })} />
                )}
              </label>
            ))}
          </div>
        </fieldset>
      ))}
      {META_ROWS.map((r) => (
        <fieldset key={r.key} className="space-y-2">
          <legend className="text-sm font-semibold">{r.label}</legend>
          {editable
            ? <RowEditor cols={r.cols} rows={metaRows(fake, r.key)} onChange={(v) => setRows({ ...rows, [r.key]: v })} />
            : <p className="text-sm">{metaRows(fake, r.key).map((x) => x.join(' ')).join(' · ')}</p>}
        </fieldset>
      ))}
      {editable && (
        <div className="sticky bottom-3 flex justify-end">
          <Button disabled={!dirty || saving} onClick={() => onSave({ fields, rows })}>{saving ? '저장 중…' : '기본 정보 저장'}</Button>
        </div>
      )}
    </div>
  )
}
