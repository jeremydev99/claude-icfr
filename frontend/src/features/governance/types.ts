/** 검토·승인 거버넌스 (ADR-0038) — 서버 `GovernanceInfo` 와 같은 모양. 판정은 서버(`can`)만 한다. */

export interface PersonRef { id: string; name: string }

export interface GovernanceCan {
  edit: boolean
  submit: boolean
  withdraw: boolean
  review: boolean
  review_return: boolean
  approve: boolean
  external_approve: boolean
  reopen_request: boolean
  reopen_decide: boolean
  reopen_external: boolean
  why: Record<string, string>
}

export interface ReopenRead {
  id: string
  requested_by: PersonRef | null
  requested_tier: number
  reason: string
  status: 'pending' | 'approved' | 'rejected'
  decided_by: PersonRef | null
  decided_at: string | null
  decision_reason: string | null
  created_at: string
}

export interface ExternalApprovalRead {
  id: string
  purpose: 'approve' | 'reopen'
  approver_body: 'ceo' | 'board'
  approved_on: string
  reference: string | null
  recorded_by: PersonRef | null
  created_at: string
  files: { id: string; filename: string; size_bytes: number }[]
}

export type ReviewPath = 'lead_then_master' | 'master' | 'external'

export interface GovernanceInfo {
  version: number
  my_tier: number
  my_tier_label: string
  review_path: ReviewPath | null
  /** 작성 중 — 내가 검토 요청하면 갈 경로 */
  preview_path?: ReviewPath | null
  requested_by: PersonRef | null
  requested_at: string | null
  reviewed_by: PersonRef | null
  reviewed_at: string | null
  confirmed_by: PersonRef | null
  pending_reopen: ReopenRead | null
  external_approvals: ExternalApprovalRead[]
  can: GovernanceCan
}

export interface GovernanceEvent {
  id: string
  action: string
  target: string | null
  actor: PersonRef | null
  reason: string | null
  before: Record<string, unknown> | null
  after: Record<string, unknown> | null
  version: number | null
  created_at: string
}

export interface InboxItem {
  entity_type: string
  entity_id: string
  title: string
  action: string
  label: string
  path: string
}
