import { useState } from 'react'
import { toast } from 'sonner'
import { AlertTriangle, CheckCircle2, FileSpreadsheet, Loader2, XCircle } from 'lucide-react'
import { useQueryClient } from '@tanstack/react-query'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import apiClient from '@/lib/axios'
import { queryKeys } from '@/lib/queryKeys'
import { useActiveTenantId } from '@/features/auth/store'
import { errorDetail } from '../api/useFs'
import { UNIT_LABEL, formatAmount } from '../fsTree.pure'
import {
  accountNames,
  categoryMapComplete,
  defaultMode,
  formFields,
  mappingCounts,
  uploadSummary,
  type UploadMode,
  type UploadParams,
} from '../upload.pure'
import type { AccountNode, AttachResponse, UploadResponse, UploadSheetCandidate, UploadStatementResult } from '../types'

const PATH: Record<UploadMode, string> = { upload: '/api/fs/upload', attach: '/api/fs/upload/attach' }
const KIND_LABEL = { disclosure_form: '공시양식', horizontal_years: '정산표(가로 연도형)' } as const
const TYPE_LABEL: Record<string, string> = { BS: '재무상태표', PL: '손익계산서', CF: '현금흐름표', SCE: '자본변동표' }

type Result = UploadResponse | AttachResponse
/** 업로드 응답에만 `sheets`(시트 후보)가 있다 — 결합 응답과 구조로 구분한다 */
const isUpload = (r: Result): r is UploadResponse => 'sheets' in r

/** 서버 오류(409·422)도 같은 모양의 본문을 `detail` 에 담아 준다 — 그대로 결과로 보여 준다 */
function bodyOf(e: unknown): Result | null {
  const d = (e as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
  return d && typeof d === 'object' && 'errors' in (d as object) ? (d as Result) : null
}

/**
 * 재무제표 엑셀 업로드 마법사 (8-D2, ADR-0037 §3).
 *
 * 파일 → 시트(자동 판별) → 옵션 → **미리보기(저장 안 함)** → 저장. 공시양식은 새로 올리고, 정산표는 이미 올린
 * 공시 재무제표에 **결합**하는 것이 기본이다(공시 행 = 부모, 정산표 COA = 잎 — 마스터 확정 D1).
 */
export default function UploadDialog({ open, onOpenChange, onDone }: {
  open: boolean
  onOpenChange: (v: boolean) => void
  onDone: (statementType: string | null, year: number | null) => void
}) {
  const queryClient = useQueryClient()
  const tenantId = useActiveTenantId()
  const [file, setFile] = useState<File | null>(null)
  const [sheets, setSheets] = useState<UploadSheetCandidate[]>([])
  const [sheet, setSheet] = useState<UploadSheetCandidate | null>(null)
  const [mode, setMode] = useState<UploadMode>('upload')
  const [unit, setUnit] = useState('')
  const [basis, setBasis] = useState('separate')
  const [includePrior, setIncludePrior] = useState(false)
  const [finalize, setFinalize] = useState(true)
  const [useSuggested, setUseSuggested] = useState(false)
  const [categoryMap, setCategoryMap] = useState<Record<string, string>>({})
  const [bridgeColumn, setBridgeColumn] = useState('')
  const [names, setNames] = useState<string[]>([])
  const [result, setResult] = useState<Result | null>(null)
  const [busy, setBusy] = useState(false)

  const reset = () => {
    setFile(null); setSheets([]); setSheet(null); setResult(null); setUnit(''); setCategoryMap({}); setBridgeColumn('')
    setUseSuggested(false); setIncludePrior(false); setFinalize(true); setBasis('separate')
  }
  const close = (v: boolean) => {
    if (!v) reset()
    onOpenChange(v)
  }

  const send = async (m: UploadMode, p: UploadParams, f = file): Promise<Result> => {
    const fd = new FormData()
    fd.append('file', f as File)
    for (const [k, v] of formFields(m, p)) fd.append(k, v)
    return (await apiClient.post<Result>(PATH[m], fd)).data
  }

  const params = (m: 'preview' | 'commit', over: Partial<UploadParams> = {}): UploadParams => ({
    mode: m, sheet: sheet?.sheet, unit: unit ? Number(unit) : null, basis, includePrior, finalize,
    mapping: useSuggested && result && isUpload(result) ? result.suggested_mapping : null,
    categoryMap, bridgeColumn: bridgeColumn || null, ...over,
  })

  const run = async (fn: () => Promise<void>) => {
    setBusy(true)
    try {
      await fn()
    } finally {
      setBusy(false)
    }
  }

  const choose = (f: File | null) => run(async () => {
    if (!f) return
    setFile(f); setResult(null); setSheet(null)
    try {
      const r = (await send('upload', { mode: 'preview' }, f)) as UploadResponse
      setSheets(r.sheets)
      if (r.sheets.length === 1) await pick(r.sheets[0], f)
      else if (!r.sheets.length) toast.error('재무제표로 보이는 시트가 없습니다(자본변동표는 지원하지 않습니다)')
    } catch (e) {
      toast.error(errorDetail(e, '엑셀 파일을 읽지 못했습니다'))
    }
  })

  const pick = async (c: UploadSheetCandidate, f = file) => {
    const m = defaultMode(c)
    setSheet(c); setMode(m); setResult(null); setCategoryMap({}); setBridgeColumn('')
    if (m === 'attach' && c.statement_type) await loadNames(c.statement_type)
    await preview(m, { sheet: c.sheet, mapping: null }, f)
  }

  const loadNames = async (stype: string) => {
    const tree = (await apiClient.get<AccountNode[]>('/api/fs/accounts', { params: { statement_type: stype } })).data
    setNames(accountNames(tree))
  }

  const preview = async (m = mode, over: Partial<UploadParams> = {}, f = file) => {
    try {
      setResult(await send(m, params('preview', over), f))
    } catch (e) {
      const b = bodyOf(e)
      if (b) setResult(b)
      else toast.error(errorDetail(e, '미리보기를 만들지 못했습니다'))
    }
  }

  const commit = () => run(async () => {
    try {
      const r = await send(mode, params('commit'))
      queryClient.invalidateQueries({ queryKey: queryKeys.fs.all(tenantId) })
      const submitted = r.statements.filter((s) => s.review_requested).map((s) => s.fiscal_year)
      toast.success(`저장했습니다 — ${r.statements.length}개 연도${submitted.length ? ` (검토 요청 ${submitted.join(', ')})` : ''}`)
      onDone(r.statement_type, r.statements[0]?.fiscal_year ?? null)
      close(false)
    } catch (e) {
      const b = bodyOf(e)
      if (b) setResult(b)
      toast.error(b?.errors?.[0] ?? errorDetail(e, '저장하지 못했습니다'))
    }
  })

  const reopen = (statementId: string) => run(async () => {
    try {
      await apiClient.post(`/api/fs/statements/${statementId}/reopen`, { reason: '정산표 결합을 위해 재오픈' })
      queryClient.invalidateQueries({ queryKey: queryKeys.fs.all(tenantId) })
      toast.success('재오픈했습니다 — 미리보기를 다시 만듭니다')
      await preview()
    } catch (e) {
      toast.error(errorDetail(e, '재오픈하지 못했습니다'))
    }
  })

  const upload = result && isUpload(result) ? result : null
  const attach = result && !isUpload(result) ? (result as AttachResponse) : null
  const needsUnit = result?.errors.some((e) => e.includes('단위')) ?? false
  const mappingOk = !upload?.mapping_required || useSuggested
  const mapOk = !attach?.unmatched.length || categoryMapComplete(attach.unmatched, categoryMap)
  const canCommit = Boolean(result) && !result!.errors.length && !result!.conflicts.length && mappingOk && mapOk && !busy

  return (
    <Dialog open={open} onOpenChange={close}>
      <DialogContent className="max-h-[90vh] max-w-3xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle>재무제표 엑셀 업로드</DialogTitle>
          <DialogDescription>
            미리보기는 저장하지 않습니다. 공시양식(재무상태표·손익계산서·현금흐름표)을 먼저 올리고, 정산표는 그 공시 재무제표에
            결합하면 공시 행 아래에 계정별 금액이 붙습니다.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 text-sm">
          <label className="flex cursor-pointer items-center gap-2 rounded border border-dashed p-3 hover:bg-muted">
            <FileSpreadsheet className="h-5 w-5 text-muted-foreground" />
            <span>{file ? file.name : '엑셀 파일(.xlsx) 선택'}</span>
            <input type="file" accept=".xlsx" className="hidden" onChange={(e) => choose(e.target.files?.[0] ?? null)} />
            {busy && <Loader2 className="ml-auto h-4 w-4 animate-spin" />}
          </label>

          {sheets.length > 1 && (
            <div>
              <p className="mb-1 text-xs text-muted-foreground">시트 선택</p>
              <div className="flex flex-wrap gap-2">
                {sheets.map((c) => (
                  <Button key={c.sheet} size="sm" variant={sheet?.sheet === c.sheet ? 'default' : 'outline'}
                    disabled={busy} onClick={() => run(() => pick(c))}>
                    {c.sheet}
                    <span className="ml-1 text-[10px] opacity-70">{KIND_LABEL[c.kind]} · {TYPE_LABEL[c.statement_type ?? ''] ?? '?'}</span>
                  </Button>
                ))}
              </div>
            </div>
          )}

          {sheet && (
            <div className="grid grid-cols-2 gap-3 rounded border p-3 text-xs md:grid-cols-4">
              <label className="space-y-1">
                <span className="text-muted-foreground">방식</span>
                <select value={mode} onChange={(e) => { const m = e.target.value as UploadMode; setMode(m); setResult(null); if (m === 'attach' && sheet.statement_type) loadNames(sheet.statement_type) }}
                  className="h-9 w-full rounded border bg-background px-2 py-1 leading-normal" disabled={sheet.kind === 'disclosure_form'}>
                  <option value="upload">새로 올리기</option>
                  {sheet.kind === 'horizontal_years' && <option value="attach">공시에 결합(권장)</option>}
                </select>
              </label>
              <label className="space-y-1">
                <span className="text-muted-foreground">단위{needsUnit && <b className="text-red-600"> (필수)</b>}</span>
                <select value={unit} onChange={(e) => setUnit(e.target.value)} className="h-9 w-full rounded border bg-background px-2 py-1 leading-normal">
                  <option value="">{upload?.unit_label ? `시트 표기(${upload.unit_label})` : '선택…'}</option>
                  {Object.entries(UNIT_LABEL).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
                </select>
              </label>
              <label className="space-y-1">
                <span className="text-muted-foreground">연결·별도</span>
                <select value={basis} onChange={(e) => setBasis(e.target.value)} className="h-9 w-full rounded border bg-background px-2 py-1 leading-normal">
                  <option value="separate">별도</option>
                  <option value="consolidated">연결</option>
                </select>
              </label>
              <div className="space-y-1">
                {mode === 'upload' && sheet.kind === 'disclosure_form' && (
                  <label className="flex items-center gap-1">
                    <input type="checkbox" checked={includePrior} onChange={(e) => setIncludePrior(e.target.checked)} />
                    전기도 저장
                  </label>
                )}
                <label className="flex items-center gap-1" title="확정은 결재선(검토 요청 → 검토 → 승인)으로만 됩니다. 정산표를 결합할 계획이면 끄세요 — 결합은 작성 중 상태에서만 됩니다">
                  <input type="checkbox" checked={finalize} onChange={(e) => setFinalize(e.target.checked)} />
                  검증 통과 시 최신 연도 검토 요청
                </label>
              </div>
              <div className="col-span-full flex justify-end">
                <Button size="sm" variant="outline" disabled={busy} onClick={() => run(() => preview())}>미리보기 다시 만들기</Button>
              </div>
            </div>
          )}

          {result && (
            <div className="space-y-3 text-xs">
              <div className="flex flex-wrap gap-x-4 gap-y-1">
                <span><b>{TYPE_LABEL[result.statement_type ?? ''] ?? result.statement_type}</b> · {result.basis === 'consolidated' ? '연결' : '별도'}</span>
                <span>단위 {result.unit ? UNIT_LABEL[result.unit] : '—'}</span>
                <span>시트 연도 {result.periods.join(', ') || '—'}</span>
                <span>저장할 연도 <b>{result.fiscal_years.join(', ') || '—'}</b></span>
                {upload && (() => {
                  const s = uploadSummary(upload)
                  return <>
                    <span>계정 {s.accounts}행</span>
                    {s.excluded.length > 0 && <span className="text-muted-foreground">제외 {s.excluded.join(', ')}</span>}
                    {s.diffs > 0 && <span className="text-amber-700">원본 소계 불일치 {s.diffs}건 → 임시계정으로 받음</span>}
                  </>
                })()}
                {attach && <>
                  <span>매핑 열 <b>{attach.bridge_column ?? '—'}</b></span>
                  <span>붙일 계정 {attach.rows.filter((r) => !r.skip_reason && r.target_name).length}행</span>
                </>}
              </div>

              {result.errors.length > 0 && <MessageList tone="error" items={result.errors} />}
              {result.warnings.length > 0 && <MessageList tone="warn" items={result.warnings} />}

              {result.conflicts.length > 0 && (
                <div className="rounded border border-red-300 bg-red-50 p-2">
                  {mode === 'attach' ? '확정된 재무제표에는 결합할 수 없습니다 — 재오픈 후 결합하세요.' : '같은 연도·종류의 재무제표가 이미 있습니다(덮어쓰지 않습니다).'}
                  <ul className="mt-1 space-y-1">
                    {result.conflicts.map((c) => (
                      <li key={c.statement_id} className="flex items-center gap-2">
                        {c.fiscal_year} · {c.status === 'final' ? '확정' : '작성 중'}
                        {mode === 'attach' && c.status === 'final' && (
                          <Button size="sm" variant="outline" disabled={busy} onClick={() => reopen(c.statement_id)}>재오픈</Button>
                        )}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {upload?.mapping_required && (() => {
                const m = mappingCounts(upload.suggested_mapping)
                return (
                  <label className="flex items-start gap-2 rounded border border-amber-300 bg-amber-50 p-2">
                    <input type="checkbox" className="mt-0.5" checked={useSuggested}
                      onChange={(e) => { setUseSuggested(e.target.checked); setTimeout(() => run(() => preview(mode, { mapping: e.target.checked ? upload.suggested_mapping : null })), 0) }} />
                    <span>이 종류의 계정이 이미 있습니다. <b>제안된 계정 대응</b>을 사용합니다 — 기존 계정 {m.existing}행, 새 계정 {m.created}행.
                      (계정 이름과 상위 계정 경로가 같고 소계 여부가 같은 것만 기존 계정으로 제안합니다)</span>
                  </label>
                )
              })()}

              {attach && attach.bridge_candidates.length > 0 && (
                <label className="flex items-center gap-2">
                  <span className="text-muted-foreground">매핑 열(정산표 → 공시 계정)</span>
                  <select value={bridgeColumn || attach.bridge_column || ''} className="h-9 rounded border bg-background px-2 py-1 leading-normal"
                    onChange={(e) => { const v = e.target.value; setBridgeColumn(v); setCategoryMap({}); setTimeout(() => run(() => preview(mode, { bridgeColumn: v || null, categoryMap: {} })), 0) }}>
                    <option value="">자동</option>
                    {attach.bridge_candidates.map((c) => (
                      <option key={c.column} value={c.column}>{c.column}열 — 값 {c.values}종, 공시 계정과 일치 {c.matched}</option>
                    ))}
                  </select>
                </label>
              )}

              {attach && attach.unmatched.length > 0 && (
                <div className="rounded border border-amber-300 bg-amber-50 p-2">
                  <p className="mb-1">매핑 값이 공시 계정 이름과 다릅니다 — 어느 공시 계정에 붙일지 고르세요(추정하지 않습니다).</p>
                  {attach.unmatched.map((v) => (
                    <label key={v} className="mb-1 flex items-center gap-2">
                      <span className="w-40 truncate">{v}</span>→
                      <select value={categoryMap[v] ?? ''} onChange={(e) => setCategoryMap({ ...categoryMap, [v]: e.target.value })}
                        className="h-9 flex-1 rounded border bg-background px-2 py-1 leading-normal">
                        <option value="">공시 계정 선택…</option>
                        {names.map((n) => <option key={n} value={n}>{n}</option>)}
                      </select>
                    </label>
                  ))}
                  <Button size="sm" variant="outline" disabled={busy || !mapOk} onClick={() => run(() => preview())}>대응표로 미리보기</Button>
                </div>
              )}

              {result.statements.length > 0 && <StatementResults items={result.statements} />}
            </div>
          )}
        </div>

        <DialogFooter>
          <Button variant="ghost" onClick={() => close(false)}>닫기</Button>
          <Button onClick={commit} disabled={!canCommit}>
            {busy && <Loader2 className="mr-1 h-4 w-4 animate-spin" />}
            {mode === 'attach' ? '결합 저장' : '저장'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function MessageList({ tone, items }: { tone: 'error' | 'warn'; items: string[] }) {
  return (
    <ul className={tone === 'error' ? 'rounded border border-red-300 bg-red-50 p-2' : 'rounded border border-amber-200 bg-amber-50/60 p-2'}>
      {items.map((m, i) => (
        <li key={i} className="flex gap-1">
          {tone === 'error' ? <XCircle className="mt-0.5 h-3 w-3 shrink-0 text-red-600" /> : <AlertTriangle className="mt-0.5 h-3 w-3 shrink-0 text-amber-600" />}
          {m}
        </li>
      ))}
    </ul>
  )
}

function StatementResults({ items }: { items: UploadStatementResult[] }) {
  return (
    <table className="w-full">
      <thead className="border-b text-muted-foreground">
        <tr><th className="py-1 text-left">연도</th><th className="text-left">검증</th><th className="text-left">임시계정(원본 차이)</th><th className="text-left">확정</th></tr>
      </thead>
      <tbody>
        {items.map((s) => (
          <tr key={s.fiscal_year} className="border-b last:border-0">
            <td className="py-1">{s.fiscal_year}</td>
            <td>
              {s.ok
                ? <span className="flex items-center gap-1 text-emerald-700"><CheckCircle2 className="h-3 w-3" />통과 · 비교 {s.checks_count}건</span>
                : <span className="text-red-700">오류 {s.errors.length}건</span>}
            </td>
            <td>{s.suspense.length ? s.suspense.map((x) => `${x.parent_name} ${formatAmount(x.amount)}`).join(' / ') : '—'}</td>
            <td>{s.review_requested ? <Badge>검토 요청됨</Badge> : s.finalize_candidate ? (s.ok ? '저장 시 검토 요청' : '작성 중으로 저장') : '작성 중'}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}
