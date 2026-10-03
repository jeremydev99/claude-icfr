/** 제안 결재 타입·표시 함수 — `proposals.test.ts`. 규칙 판정은 서버(`can`). */

export interface PersonRef { id: string; name: string }

export interface ProposalItem {
  id: string
  sort_order: number
  account_id: string | null
  statement_type: string | null
  account_name: string
  group_label: string | null
  action: 'link' | 'manual'
  template_account_id: string | null
  template_name: string | null
  rationale: string
  decision: 'pending' | 'accepted' | 'rejected' | 'modified'
  decided_by: PersonRef | null
  decided_at: string | null
  decision_note: string | null
  final_template_account_id: string | null
  final_template_name: string | null
}

export interface Proposal {
  id: string
  kind: string
  title: string
  summary: string | null
  status: 'pending_review' | 'reviewed' | 'approved' | 'returned'
  status_label: string
  proposed_by: string
  reviewed_by: PersonRef | null
  approved_by: PersonRef | null
  closed_reason: string | null
  result: Record<string, unknown> | null
  created_at: string
  counts: Record<string, number>
  items: ProposalItem[]
  can: { decide: boolean; review_done: boolean; approve: boolean; return_: boolean; why: Record<string, string> } | null
}

export const DECISION_LABEL: Record<string, string> = {
  pending: '미결정', accepted: '승인', rejected: '반려', modified: '변경',
}

export function decisionCounts(items: Pick<ProposalItem, 'decision'>[]) {
  const c = { total: items.length, pending: 0, accepted: 0, rejected: 0, modified: 0 }
  for (const i of items) c[i.decision] += 1
  return c
}

/** 제안자 표기 — 시스템 행위자는 사람이 읽는 이름으로 */
export function proposerLabel(actor: string): string {
  if (actor === 'system:claude-proposal') return 'Claude(AI) 초안'
  return actor.startsWith('system:') ? `시스템(${actor.slice(7)})` : actor
}
