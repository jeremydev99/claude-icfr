/**
 * 스코핑 템플릿 연결 (8-D3, ADR-0037 §4) — 순수 로직. `match.test.ts`.
 *
 * 제안은 서버가 계산하고 **저장하지 않는다**. 사람이 확인한 것만 `POST /template-links` 로 보낸다.
 * 근거(exact/normalized/manual)는 서버가 판정한다 — 여기서는 보내지 않는다.
 */

export interface TemplateLink {
  id: string
  account_id: string
  template_account_id: string
  template_name: string | null
  basis: 'exact' | 'normalized' | 'manual'
  confirmed_at: string
  note: string | null
}

export interface MatchRow {
  account_id: string
  name: string
  parent_name: string | null
  depth: number
  is_subtotal: boolean
  link: TemplateLink | null
  suggestion: { template_account_id: string; template_name: string; basis: 'exact' | 'normalized' } | null
}

export interface TemplateAccount {
  id: string
  name: string
  group_label: string | null
  sort_order: number
  linked_count: number
}

export interface TemplateMatches {
  template_code: string
  template_version: number
  statement_type: string
  accounts: MatchRow[]
  template_accounts: TemplateAccount[]
  counts: Record<string, number>
}

export type MatchFilter = 'all' | 'unlinked' | 'suggested' | 'linked'

export const BASIS_LABEL: Record<string, string> = { exact: '정확일치', normalized: '정규화일치', manual: '수동' }

/** 일괄 확정 대상 — 아직 연결 안 됐고 제안이 있는 행. `bases` 로 근거를 거른다(기본: 정확일치만) */
export function bulkLinks(rows: MatchRow[], bases: string[] = ['exact']): { account_id: string; template_account_id: string }[] {
  return rows
    .filter((r) => !r.link && r.suggestion && bases.includes(r.suggestion.basis))
    .map((r) => ({ account_id: r.account_id, template_account_id: r.suggestion!.template_account_id }))
}

export function filterRows(rows: MatchRow[], f: MatchFilter): MatchRow[] {
  switch (f) {
    case 'unlinked': return rows.filter((r) => !r.link)
    case 'suggested': return rows.filter((r) => !r.link && r.suggestion)
    case 'linked': return rows.filter((r) => r.link)
    default: return rows
  }
}

/** 템플릿 계정 선택지 — 그룹 라벨로 묶는다(원천 엑셀의 소계 행) */
export function groupedTemplates(t: TemplateAccount[]): [string, TemplateAccount[]][] {
  const m = new Map<string, TemplateAccount[]>()
  for (const a of [...t].sort((x, y) => x.sort_order - y.sort_order)) {
    const g = a.group_label ?? '(그룹 없음)'
    m.set(g, [...(m.get(g) ?? []), a])
  }
  return [...m.entries()]
}
