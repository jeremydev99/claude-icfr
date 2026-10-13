import { useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { Loader2, Upload } from 'lucide-react'
import { toast } from 'sonner'
import apiClient from '@/lib/axios'
import { queryKeys } from '@/lib/queryKeys'
import { useActiveTenantId } from '@/features/auth/store'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog'

const STMT: Record<string, string> = { BS: '재무상태표', PL: '손익계산서', NOTE: '주석', CF: '현금흐름' }

interface Field { field: string; label: string; before: string | null; after: string | null }
interface Change { key: string; statement_type: string; account_id: string; account_name: string; excel_name: string; excel_row: number; how: string; fields: Field[] }
interface ExcelOnly { key: string; statement_type: string; row: number; name: string; group: string | null }
interface AccountOnly { id: string; statement_type: string; name: string; group_label: string | null; not_applicable: boolean }
interface Result {
  mode: 'preview' | 'commit'; matched: number; changed_count: number; summary_text: string
  changes: Change[]; excel_only: ExcelOnly[]; account_only: AccountOnly[]
  skipped: { account_name: string; excel_name: string; reason: string }[]; warnings: string[]
  by_statement: Record<string, { excel: number; matched: number; changed: number }>
}

function errText(e: unknown, fallback: string): string {
  const d = (e as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
  return typeof d === 'string' ? d : fallback
}

/**
 * 스코핑 엑셀 갱신 업로드(13.9-118) — 정리본(원천 실무 양식)의 질적 10요소·판단 근거·결론을 계정에 반영한다.
 * 미리보기는 아무것도 바꾸지 않는다. 못 맞춘 엑셀 행은 같은 표의 남은 계정 중에서 골라 연결한다(다시 미리보기).
 * 금액은 반영하지 않는다(확정 재무제표가 원천). 규칙은 서버 `services/scoping_excel`.
 */
export default function ScopingExcelDialog({ scopingId, open, onOpenChange }: {
  scopingId: string; open: boolean; onOpenChange: (v: boolean) => void
}) {
  const tenantId = useActiveTenantId()
  const queryClient = useQueryClient()
  const [file, setFile] = useState<File | null>(null)
  const [links, setLinks] = useState<Record<string, string>>({})
  const [result, setResult] = useState<Result | null>(null)
  const [busy, setBusy] = useState(false)

  const reset = () => { setFile(null); setLinks({}); setResult(null) }
  const send = async (mode: 'preview' | 'commit', withLinks = links) => {
    if (!file) return
    setBusy(true)
    try {
      const fd = new FormData()
      fd.append('file', file)
      fd.append('mode', mode)
      fd.append('links', JSON.stringify(withLinks))
      const res = await apiClient.post<Result>(`/api/scoping/${scopingId}/upload-excel`, fd)
      setResult(res.data)
      if (mode === 'commit') {
        toast.success(`스코핑에 반영했습니다 — ${res.data.summary_text}`)
        queryClient.invalidateQueries({ queryKey: queryKeys.scoping.all(tenantId) })
      }
    } catch (e) {
      toast.error(errText(e, mode === 'commit' ? '반영하지 못했습니다' : '엑셀을 읽지 못했습니다'))
    } finally {
      setBusy(false)
    }
  }
  const setLink = (key: string, accountId: string) => {
    const next = { ...links }
    if (accountId) next[key] = accountId
    else delete next[key]
    setLinks(next)
    void send('preview', next)
  }
  const done = result?.mode === 'commit'
  // 이미 다른 엑셀 행에 고른 계정은 목록에서 뺀다
  const chosen = new Set(Object.values(links))

  return (
    <Dialog open={open} onOpenChange={(v) => { if (!v) reset(); onOpenChange(v) }}>
      <DialogContent className="max-h-[90vh] max-w-5xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle>스코핑 엑셀 업로드</DialogTitle>
          <DialogDescription>
            정리한 스코핑 엑셀(원천 양식: 2.1 BS · 2.2 PL · 2.3 주석 · 2.4 현금흐름)의 질적 10요소·판단 근거·유의성 결론을 계정에 반영합니다.
            금액은 반영하지 않습니다(확정 재무제표 값 유지). 엑셀에 없는 계정은 그대로 둡니다.
          </DialogDescription>
        </DialogHeader>

        {!done && (
          <div className="flex flex-wrap items-center gap-2">
            <input type="file" accept=".xlsx" aria-label="스코핑 엑셀 파일"
              onChange={(e) => { setFile(e.target.files?.[0] ?? null); setResult(null); setLinks({}) }}
              className="text-sm file:mr-2 file:rounded-md file:border file:bg-background file:px-3 file:py-1" />
            <Button size="sm" variant="outline" disabled={!file || busy} onClick={() => send('preview')}>
              {busy ? <Loader2 className="mr-1 h-4 w-4 animate-spin" /> : <Upload className="mr-1 h-4 w-4" />}미리보기
            </Button>
          </div>
        )}

        {result && (
          <div className="space-y-4 text-sm">
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
              {Object.entries(result.by_statement).map(([st, b]) => (
                <div key={st} className="rounded-md border p-2">
                  <div className="text-xs text-muted-foreground">{STMT[st] ?? st}</div>
                  <div className="font-medium">변경 {b.changed}</div>
                  <div className="text-xs text-muted-foreground">엑셀 {b.excel} · 맞춤 {b.matched}</div>
                </div>
              ))}
            </div>

            {result.excel_only.length > 0 && !done && (
              <section className="space-y-1">
                <h3 className="font-medium">계정을 못 맞춘 엑셀 행 {result.excel_only.length}개 — 같은 표의 계정을 고르면 연결됩니다</h3>
                <ul className="divide-y rounded-md border">
                  {result.excel_only.map((x) => {
                    const opts = result.account_only.filter((a) => a.statement_type === x.statement_type && (!chosen.has(a.id) || links[x.key] === a.id))
                    return (
                      <li key={x.key} className="flex flex-wrap items-center gap-2 px-2 py-1.5">
                        <span className="w-20 text-xs text-muted-foreground">{STMT[x.statement_type]} {x.row}행</span>
                        <span className="min-w-[12rem] flex-1">{x.name} {x.group && <span className="text-xs text-muted-foreground">({x.group})</span>}</span>
                        <select aria-label={`${x.name} 연결`} value={links[x.key] ?? ''} disabled={busy}
                          onChange={(e) => setLink(x.key, e.target.value)}
                          className="h-8 min-w-[14rem] rounded-md border bg-background px-2 text-xs">
                          <option value="">연결 안 함 (반영하지 않음)</option>
                          {opts.map((a) => (
                            <option key={a.id} value={a.id}>{a.name}{a.group_label ? ` (${a.group_label})` : ''}{a.not_applicable ? ' · 해당 없음' : ''}</option>
                          ))}
                        </select>
                      </li>
                    )
                  })}
                </ul>
              </section>
            )}
            {Object.keys(links).length > 0 && result.excel_only.length === 0 && !done && (
              <p className="text-xs text-muted-foreground">못 맞춘 엑셀 행을 모두 연결했습니다.</p>
            )}

            <section className="space-y-1">
              <h3 className="font-medium">{done ? '반영한 계정' : '바뀌는 계정'} {result.changes.length}개</h3>
              {result.changes.length === 0 ? (
                <p className="text-muted-foreground">바뀌는 것이 없습니다.</p>
              ) : (
                <div className="max-h-80 overflow-y-auto rounded-md border">
                  <table className="w-full text-xs">
                    <thead className="sticky top-0 bg-muted text-muted-foreground">
                      <tr><th className="px-2 py-1 text-left">표</th><th className="px-2 text-left">계정 (엑셀)</th><th className="px-2 text-left">항목</th><th className="px-2 text-left">전</th><th className="px-2 text-left">후</th></tr>
                    </thead>
                    <tbody>
                      {result.changes.flatMap((c) => c.fields.map((f, i) => (
                        <tr key={`${c.key}-${f.field}`} className="border-t align-top">
                          {i === 0 && <td rowSpan={c.fields.length} className="px-2 py-1">{STMT[c.statement_type]}</td>}
                          {i === 0 && (
                            <td rowSpan={c.fields.length} className="px-2 py-1 font-medium">
                              {c.account_name}
                              {c.excel_name !== c.account_name && <div className="font-normal text-muted-foreground">엑셀: {c.excel_name}</div>}
                              <div className="font-normal text-muted-foreground">{c.how}</div>
                            </td>
                          )}
                          <td className="px-2 py-1">{f.label}</td>
                          <td className={f.field === 'ratings' ? 'px-2 py-1 font-mono tracking-wider text-muted-foreground' : 'max-w-[16rem] px-2 py-1 text-muted-foreground'}>{f.before ?? '—'}</td>
                          <td className={f.field === 'ratings' ? 'px-2 py-1 font-mono tracking-wider' : 'max-w-[16rem] px-2 py-1'}>{f.after ?? '—'}</td>
                        </tr>
                      )))}
                    </tbody>
                  </table>
                </div>
              )}
              <p className="text-xs text-muted-foreground">질적 10요소는 요소 순서대로 등급(H·M·L), 빈칸은 · 입니다. 수동 판정은 유의성 결론이 계산 결론과 다를 때만 들어갑니다.</p>
            </section>

            {result.skipped.length > 0 && (
              <details className="rounded-md border px-2 py-1">
                <summary className="cursor-pointer">반영하지 않는 계정 {result.skipped.length}개</summary>
                <ul className="mt-1 list-disc pl-5 text-xs text-muted-foreground">
                  {result.skipped.map((s) => <li key={s.account_name + s.excel_name}>{s.account_name} — {s.reason}</li>)}
                </ul>
              </details>
            )}
            {result.account_only.length > 0 && (
              <details className="rounded-md border px-2 py-1">
                <summary className="cursor-pointer">엑셀에 없는 스코핑 계정 {result.account_only.length}개 — 그대로 둡니다</summary>
                <ul className="mt-1 list-disc pl-5 text-xs text-muted-foreground">
                  {result.account_only.map((a) => <li key={a.id}>{STMT[a.statement_type]} · {a.name}{a.group_label ? ` (${a.group_label})` : ''}{a.not_applicable ? ' · 해당 없음' : ''}</li>)}
                </ul>
              </details>
            )}
            {result.warnings.length > 0 && (
              <details className="rounded-md border border-warning/40 bg-warning/5 px-2 py-1">
                <summary className="cursor-pointer text-warning">확인할 점 {result.warnings.length}개</summary>
                <ul className="mt-1 list-disc pl-5 text-xs">
                  {result.warnings.map((w) => <li key={w}>{w}</li>)}
                </ul>
              </details>
            )}

            <div className="flex justify-end gap-2">
              {done ? (
                <Button size="sm" onClick={() => { reset(); onOpenChange(false) }}>닫기</Button>
              ) : (
                <Button size="sm" disabled={busy || result.changed_count === 0}
                  onClick={() => {
                    if (window.confirm(`계정 ${result.changed_count}개를 엑셀 값으로 바꿉니다. 바뀐 칸은 '수정됨'으로 남고 이력에 기록됩니다. 반영할까요?`)) void send('commit')
                  }}>
                  스코핑에 반영 (계정 {result.changed_count}개)
                </Button>
              )}
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  )
}
