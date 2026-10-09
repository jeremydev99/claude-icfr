import { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight, Download, Loader2, RotateCcw, Search, ShieldCheck } from 'lucide-react'
import apiClient from '@/lib/axios'
import { cn } from '@/lib/utils'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { useActiveTenantId } from '@/features/auth/store'
import { toast } from 'sonner'
import HelpButton from '@/features/help/HelpButton'

interface LogRow {
  id: string
  occurred_at: string
  user_id: string | null
  user_name: string | null
  user_email: string | null
  method: string
  module: string
  action: string
  route: string
  path: string
  target_id: string | null
  /** 기록 시점 대상 이름 — '통제 EL-010-10-10 매출 인식', 'EUC 매출 집계표', '처리 12건' */
  target_label: string | null
  status_code: number
  success: boolean
  ip: string | null
  user_agent: string | null
  duration_ms: number | null
}

interface PageResp {
  items: LogRow[]
  total: number
  page: number
  size: number
  modules: string[]
  actions: string[]
  users: { id: string; name: string }[]
}

const SIZES = [10, 20, 50, 100]
const EMPTY = { q: '', user_id: '', module: '', action: '', result: '', date_from: '', date_to: '' }
type Filters = typeof EMPTY

const fmt = (iso: string) => {
  const d = new Date(iso)
  const p = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`
}
const params = (f: Filters) => Object.fromEntries(Object.entries(f).filter(([, v]) => v))

/** 감사 로그 (2026-10-06) — 사용자 활동(등록·수정·삭제·승인·로그인·다운로드) 전체. 내부회계관리자·시스템관리자만 */
export default function AuditLogsPage() {
  const tid = useActiveTenantId()
  const [draft, setDraft] = useState<Filters>(EMPTY)
  const [filters, setFilters] = useState<Filters>(EMPTY)
  const [page, setPage] = useState(1)
  const [size, setSize] = useState(20)
  const [open, setOpen] = useState<string | null>(null)
  const { data, isLoading, isError, error, isFetching } = useQuery({
    queryKey: ['audit-logs', tid, filters, page, size],
    queryFn: async () => (await apiClient.get<PageResp>('/api/admin/audit-logs', { params: { ...params(filters), page, size } })).data,
    placeholderData: (prev) => prev,
  })
  const pages = data ? Math.max(1, Math.ceil(data.total / size)) : 1
  useEffect(() => { if (page > pages) setPage(pages) }, [page, pages])

  const apply = () => { setFilters(draft); setPage(1) }
  const reset = () => { setDraft(EMPTY); setFilters(EMPTY); setPage(1) }
  const exportCsv = async () => {
    try {
      const r = await apiClient.get('/api/admin/audit-logs/export', { params: params(filters), responseType: 'blob' })
      const a = document.createElement('a')
      a.href = URL.createObjectURL(r.data as Blob)
      a.download = `audit-log-${new Date().toISOString().slice(0, 10)}.csv`
      a.click()
      URL.revokeObjectURL(a.href)
    } catch {
      toast.error('내보내지 못했습니다')
    }
  }
  const denied = isError && (error as { response?: { status?: number } })?.response?.status === 403

  return (
    <div className="mx-auto max-w-[1400px] space-y-5 p-6 md:p-8">
      <div>
        <h1 className="flex items-center gap-2 text-2xl font-bold tracking-tight"><ShieldCheck className="h-6 w-6 text-primary" />감사 로그<HelpButton k="screen.admin.audit-logs.filters" /></h1>
        <p className="mt-1 text-sm text-muted-foreground">
          사용자가 시스템에서 한 일(등록·수정·삭제·승인·확정·로그인·다운로드)이 시간순으로 남습니다. 화면을 보기만 한 기록은 남기지 않습니다.
          기록은 지우거나 고칠 수 없습니다. 로그인 실패·잠금은 담당자/권한 › 로그인 기록에서 더 자세히 볼 수 있습니다.
        </p>
      </div>

      {denied ? (
        <p className="rounded-lg border p-6 text-sm text-muted-foreground">감사 로그는 내부회계관리자·시스템관리자만 볼 수 있습니다.</p>
      ) : (
        <>
          <form className="grid gap-2 rounded-xl border bg-card p-4 shadow-card sm:grid-cols-2 lg:grid-cols-4" onSubmit={(e) => { e.preventDefault(); apply() }}>
            <label className="relative lg:col-span-2">
              <Search className="absolute left-2.5 top-3 h-4 w-4 text-muted-foreground" />
              <Input value={draft.q} onChange={(e) => setDraft({ ...draft, q: e.target.value })} placeholder="검색 — 사용자·동작·대상(통제 코드·이름)·IP" className="pl-8" />
            </label>
            <Sel value={draft.user_id} onChange={(v) => setDraft({ ...draft, user_id: v })} all="사용자 전체"
              options={(data?.users ?? []).map((u) => ({ value: u.id, label: u.name }))} />
            <Sel value={draft.module} onChange={(v) => setDraft({ ...draft, module: v })} all="모듈 전체"
              options={(data?.modules ?? []).map((m) => ({ value: m, label: m }))} />
            <Sel value={draft.action} onChange={(v) => setDraft({ ...draft, action: v })} all="동작 전체"
              options={(data?.actions ?? []).map((m) => ({ value: m, label: m }))} />
            <Sel value={draft.result} onChange={(v) => setDraft({ ...draft, result: v })} all="결과 전체"
              options={[{ value: 'success', label: '성공' }, { value: 'fail', label: '실패' }]} />
            <div className="flex items-center gap-1.5 text-sm">
              <Input type="date" value={draft.date_from} onChange={(e) => setDraft({ ...draft, date_from: e.target.value })} aria-label="시작일" className="min-w-0 px-2" />
              <span className="text-muted-foreground">~</span>
              <Input type="date" value={draft.date_to} onChange={(e) => setDraft({ ...draft, date_to: e.target.value })} aria-label="종료일" className="min-w-0 px-2" />
            </div>
            <div className="flex gap-2">
              <Button type="submit" className="flex-1">검색</Button>
              <Button type="button" variant="outline" onClick={reset} title="조건 초기화"><RotateCcw className="h-4 w-4" /></Button>
            </div>
          </form>

          <div className="flex flex-wrap items-center gap-3 text-sm">
            <span className="inline-flex items-center gap-1">총 <b>{(data?.total ?? 0).toLocaleString()}</b>건<HelpButton k="screen.admin.audit-logs.list" /></span>
            {isFetching && <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />}
            <label className="ml-auto flex items-center gap-1.5">
              한 페이지
              <select value={size} onChange={(e) => { setSize(Number(e.target.value)); setPage(1) }} className="h-8 rounded-md border bg-background px-2 py-0">
                {SIZES.map((s) => <option key={s} value={s}>{s}건</option>)}
              </select>
            </label>
            <Button size="sm" variant="outline" onClick={exportCsv}><Download className="mr-1.5 h-4 w-4" />CSV 내보내기</Button>
          </div>

          <div className="overflow-x-auto rounded-xl border bg-card shadow-card">
            <table className="w-full min-w-[960px] text-sm">
              <thead className="border-b bg-muted/50 text-left">
                <tr>
                  <th className="px-3 py-2 font-semibold">일시</th>
                  <th className="px-3 py-2 font-semibold">사용자</th>
                  <th className="px-3 py-2 font-semibold">모듈</th>
                  <th className="px-3 py-2 font-semibold">동작</th>
                  <th className="px-3 py-2 font-semibold">결과</th>
                  <th className="px-3 py-2 font-semibold">대상</th>
                  <th className="px-3 py-2 font-semibold">IP</th>
                </tr>
              </thead>
              <tbody>
                {isLoading && <tr><td colSpan={7} className="p-8 text-center"><Loader2 className="mx-auto h-5 w-5 animate-spin" /></td></tr>}
                {!isLoading && (data?.items.length ?? 0) === 0 && (
                  <tr><td colSpan={7} className="p-8 text-center text-muted-foreground">조건에 맞는 기록이 없습니다</td></tr>
                )}
                {data?.items.map((r) => (
                  <FragmentRow key={r.id} r={r} open={open === r.id} onToggle={() => setOpen(open === r.id ? null : r.id)} />
                ))}
              </tbody>
            </table>
          </div>

          <nav className="flex flex-wrap items-center justify-center gap-1" aria-label="페이지">
            <Button size="icon" variant="ghost" disabled={page <= 1} onClick={() => setPage(1)} aria-label="처음"><ChevronsLeft className="h-4 w-4" /></Button>
            <Button size="icon" variant="ghost" disabled={page <= 1} onClick={() => setPage(page - 1)} aria-label="이전"><ChevronLeft className="h-4 w-4" /></Button>
            {pageWindow(page, pages).map((p, i) => p === 0
              ? <span key={`gap${i}`} className="px-1 text-muted-foreground">…</span>
              : <Button key={p} size="sm" variant={p === page ? 'default' : 'ghost'} className="min-w-9" onClick={() => setPage(p)}>{p}</Button>)}
            <Button size="icon" variant="ghost" disabled={page >= pages} onClick={() => setPage(page + 1)} aria-label="다음"><ChevronRight className="h-4 w-4" /></Button>
            <Button size="icon" variant="ghost" disabled={page >= pages} onClick={() => setPage(pages)} aria-label="마지막"><ChevronsRight className="h-4 w-4" /></Button>
            <span className="ml-2 text-xs text-muted-foreground">{page} / {pages}</span>
          </nav>
        </>
      )}
    </div>
  )
}

/** 현재 페이지 주변 번호 + 처음·끝, 사이는 0(…) */
export function pageWindow(page: number, pages: number): number[] {
  const set = new Set([1, pages, page - 2, page - 1, page, page + 1, page + 2].filter((p) => p >= 1 && p <= pages))
  const sorted = [...set].sort((a, b) => a - b)
  const out: number[] = []
  sorted.forEach((p, i) => { if (i && p - sorted[i - 1] > 1) out.push(0); out.push(p) })
  return out
}

function FragmentRow({ r, open, onToggle }: { r: LogRow; open: boolean; onToggle: () => void }) {
  return (
    <>
      <tr className={cn('cursor-pointer border-b hover:bg-muted/40', open && 'bg-accent/40')} onClick={onToggle}>
        <td className="whitespace-nowrap px-3 py-2 font-mono text-xs">{fmt(r.occurred_at)}</td>
        <td className="px-3 py-2">{r.user_name ?? <span className="text-muted-foreground">(알 수 없음)</span>}
          {r.user_email && <span className="block text-xs text-muted-foreground">{r.user_email}</span>}</td>
        <td className="px-3 py-2">{r.module}</td>
        <td className="px-3 py-2 font-medium">{r.action}</td>
        <td className="px-3 py-2">
          <Badge variant="outline" className={r.success ? 'border-emerald-300 text-emerald-700 dark:text-emerald-300' : 'border-rose-300 text-rose-700 dark:text-rose-300'}>
            {r.success ? '성공' : '실패'} {r.status_code}
          </Badge>
        </td>
        <td className="max-w-[360px] px-3 py-2" title={r.path}>
          {r.target_label
            ? <span className="line-clamp-2">{r.target_label}</span>
            : <span className="block truncate font-mono text-xs text-muted-foreground">{r.path}</span>}
        </td>
        <td className="whitespace-nowrap px-3 py-2 font-mono text-xs">{r.ip ?? '-'}</td>
      </tr>
      {open && (
        <tr className="border-b bg-muted/30">
          <td colSpan={7} className="px-4 py-3 text-xs">
            <dl className="grid gap-x-6 gap-y-1 sm:grid-cols-2">
              <div><dt className="inline text-muted-foreground">요청 </dt><dd className="inline font-mono">{r.method} {r.route}</dd></div>
              <div><dt className="inline text-muted-foreground">경로 </dt><dd className="inline font-mono">{r.path}</dd></div>
              <div><dt className="inline text-muted-foreground">대상 ID </dt><dd className="inline font-mono">{r.target_id ?? '-'}</dd></div>
              <div><dt className="inline text-muted-foreground">처리 시간 </dt><dd className="inline">{r.duration_ms ?? '-'}ms</dd></div>
              <div className="sm:col-span-2"><dt className="inline text-muted-foreground">기기 </dt><dd className="inline">{r.user_agent ?? '-'}</dd></div>
            </dl>
          </td>
        </tr>
      )}
    </>
  )
}

function Sel({ value, onChange, options, all }: { value: string; onChange: (v: string) => void; options: { value: string; label: string }[]; all: string }) {
  return (
    <select value={value} onChange={(e) => onChange(e.target.value)} className="h-10 rounded-md border bg-background px-2 py-0 text-sm">
      <option value="">{all}</option>
      {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
    </select>
  )
}
