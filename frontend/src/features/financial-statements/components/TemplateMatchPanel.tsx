import { useState } from 'react'
import { toast } from 'sonner'
import { Link2, Link2Off, Loader2 } from 'lucide-react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import apiClient from '@/lib/axios'
import { queryKeys } from '@/lib/queryKeys'
import { useActiveTenantId } from '@/features/auth/store'
import { cn } from '@/lib/utils'
import { errorDetail } from '../api/useFs'
import {
  BASIS_LABEL,
  bulkLinks,
  filterRows,
  groupedTemplates,
  type MatchFilter,
  type MatchRow,
  type TemplateMatches,
} from '../match.pure'

/**
 * 스코핑 템플릿 연결 (8-D3, ADR-0037 §4) — 회사 계정 ↔ 스코핑 표준 템플릿 계정.
 *
 * 자동 제안은 **저장되지 않는다.** 사람이 확정한 연결만 남고, 확정된 연결만 스코핑(8-E)이 기본값을 가져온다.
 * 근거(정확일치·정규화일치·수동)는 서버가 이름 규칙으로 판정한다.
 */
export default function TemplateMatchPanel({ statementType, canEdit }: { statementType: string; canEdit: boolean }) {
  const tenantId = useActiveTenantId()
  const queryClient = useQueryClient()
  const [filter, setFilter] = useState<MatchFilter>('unlinked')
  const { data, isLoading } = useQuery({
    queryKey: queryKeys.fs.matches(tenantId, statementType),
    queryFn: async () => (await apiClient.get<TemplateMatches>('/api/fs/template-matches', {
      params: { statement_type: statementType },
    })).data,
  })
  const refresh = () => queryClient.invalidateQueries({ queryKey: queryKeys.fs.matches(tenantId, statementType) })
  const link = useMutation({
    mutationFn: async (links: { account_id: string; template_account_id: string }[]) =>
      (await apiClient.post<{ links: unknown[]; warnings: string[] }>('/api/fs/template-links', {
        template_code: data?.template_code, template_version: data?.template_version, links,
      })).data,
    onSuccess: (r) => {
      toast.success(`연결 ${r.links.length}건을 확정했습니다`)
      r.warnings.forEach((w) => toast.warning(w))
      refresh()
    },
    onError: (e) => toast.error(errorDetail(e, '연결하지 못했습니다')),
  })
  const unlink = useMutation({
    mutationFn: async (id: string) => apiClient.delete(`/api/fs/template-links/${id}`),
    onSuccess: () => { toast.success('연결을 해제했습니다'); refresh() },
    onError: (e) => toast.error(errorDetail(e, '해제하지 못했습니다')),
  })

  if (isLoading) return <Loader2 className="h-5 w-5 animate-spin" />
  if (!data) return null
  const exact = bulkLinks(data.accounts, ['exact'])
  const rows = filterRows(data.accounts, filter)
  const groups = groupedTemplates(data.template_accounts)
  const unusedTemplates = data.template_accounts.filter((t) => t.linked_count === 0)
  const c = data.counts

  return (
    <div className="space-y-3 text-xs">
      <div className="flex flex-wrap items-center gap-3">
        <span className="text-muted-foreground">템플릿 {data.template_code} v{data.template_version}</span>
        <span>회사 계정 {c.accounts ?? 0} · 연결 <b>{c.linked ?? 0}</b> · 제안(정확) {c.suggested_exact ?? 0} ·
          제안(정규화) {c.suggested_normalized ?? 0} · 제안 없음 {c.unmatched ?? 0}</span>
        <select value={filter} onChange={(e) => setFilter(e.target.value as MatchFilter)}
          className="h-9 rounded border bg-background px-2 py-1 leading-normal" aria-label="보기">
          <option value="unlinked">미연결</option>
          <option value="suggested">제안 있는 미연결</option>
          <option value="linked">연결됨</option>
          <option value="all">전체</option>
        </select>
        {canEdit && (
          <Button size="sm" className="ml-auto" disabled={!exact.length || link.isPending}
            onClick={() => link.mutate(exact)}>
            <Link2 className="mr-1 h-4 w-4" />정확일치 제안 {exact.length}건 일괄 확정
          </Button>
        )}
      </div>
      <p className="text-muted-foreground">
        자동 제안은 저장되지 않습니다 — 확정한 연결만 스코핑에서 질적 평가값·판단 근거의 기본값으로 쓰입니다.
        정규화일치(괄호·접미 차이)와 제안 없는 계정은 하나씩 확인해 연결하세요.
      </p>
      <table className="w-full">
        <thead className="border-b text-muted-foreground">
          <tr>
            <th className="py-1.5 text-left font-medium">회사 계정</th>
            <th className="text-left font-medium">연결 / 제안</th>
            <th className="w-80 text-left font-medium">{canEdit ? '템플릿 계정 선택' : ''}</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <MatchLine key={`${r.account_id}:${r.link?.id ?? ""}`} row={r} groups={groups} canEdit={canEdit}
              busy={link.isPending || unlink.isPending}
              onLink={(t) => link.mutate([{ account_id: r.account_id, template_account_id: t }])}
              onUnlink={(id) => unlink.mutate(id)} />
          ))}
          {!rows.length && <tr><td colSpan={3} className="py-6 text-center text-muted-foreground">해당하는 계정이 없습니다.</td></tr>}
        </tbody>
      </table>
      {unusedTemplates.length > 0 && (
        <details className="rounded border px-3 py-2">
          <summary className="cursor-pointer text-muted-foreground">연결되지 않은 템플릿 계정 {unusedTemplates.length}건</summary>
          <p className="mt-2 leading-relaxed">{unusedTemplates.map((t) => t.name).join(' · ')}</p>
        </details>
      )}
    </div>
  )
}

function MatchLine({ row, groups, canEdit, busy, onLink, onUnlink }: {
  row: MatchRow
  groups: ReturnType<typeof groupedTemplates>
  canEdit: boolean
  busy: boolean
  onLink: (templateAccountId: string) => void
  onUnlink: (linkId: string) => void
}) {
  const [pick, setPick] = useState(row.link?.template_account_id ?? row.suggestion?.template_account_id ?? '')
  return (
    <tr className={cn('border-b last:border-0', row.link && 'bg-emerald-50/40')}>
      <td className="py-1.5">
        <span style={{ paddingLeft: row.depth * 12 }} className={cn(row.is_subtotal && 'font-semibold')}>{row.name}</span>
        {row.parent_name && <span className="ml-2 text-[10px] text-muted-foreground">{row.parent_name}</span>}
      </td>
      <td>
        {row.link ? (
          <span className="flex items-center gap-1">
            <Badge variant="default">{BASIS_LABEL[row.link.basis]}</Badge>{row.link.template_name}
          </span>
        ) : row.suggestion ? (
          <span className="flex items-center gap-1 text-muted-foreground">
            <Badge variant="outline">제안 · {BASIS_LABEL[row.suggestion.basis]}</Badge>{row.suggestion.template_name}
          </span>
        ) : <span className="text-muted-foreground">—</span>}
      </td>
      <td>
        {canEdit && (
          <div className="flex items-center gap-1">
            <select value={pick} onChange={(e) => setPick(e.target.value)}
              className="h-9 min-w-0 flex-1 rounded border bg-background px-2 py-1 leading-normal">
              <option value="">템플릿 계정…</option>
              {groups.map(([g, list]) => (
                <optgroup key={g} label={g}>
                  {list.map((t) => <option key={t.id} value={t.id}>{t.name}{t.linked_count ? ` (연결 ${t.linked_count})` : ''}</option>)}
                </optgroup>
              ))}
            </select>
            <Button size="sm" variant="outline" disabled={!pick || busy || pick === row.link?.template_account_id}
              onClick={() => onLink(pick)}>{row.link ? '변경' : '확정'}</Button>
            {row.link && (
              <Button size="sm" variant="ghost" disabled={busy} onClick={() => onUnlink(row.link!.id)} aria-label="연결 해제">
                <Link2Off className="h-4 w-4" />
              </Button>
            )}
          </div>
        )}
      </td>
    </tr>
  )
}
