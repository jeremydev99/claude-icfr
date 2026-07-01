// ── Deficiency ─────────────────────────────────────────────

export type DeficiencySeverity = 'low' | 'medium' | 'high'
export type DeficiencyStatus = 'open' | 'in_progress' | 'closed'

export interface Deficiency {
  id: string
  code: string
  severity: DeficiencySeverity
  description: string
  status: DeficiencyStatus
  fiscal_year: number
  test_run_id: string | null
  control_id: string | null
  final_conclusion: string | null
  confirmed_at: string | null
  confirmed_by_id: string | null
  created_at: string
  updated_at: string
}

export interface DeficiencyCreatePayload {
  code: string
  severity: DeficiencySeverity
  description: string
  status?: DeficiencyStatus
  fiscal_year?: number
  test_run_id?: string | null
  control_id?: string | null
}

export interface DeficiencyUpdatePayload {
  severity?: DeficiencySeverity
  description?: string
  status?: DeficiencyStatus
  fiscal_year?: number
  control_id?: string | null
  final_conclusion?: string | null
  confirmed_at?: string | null
  confirmed_by_id?: string | null
}

export interface DeficiencyListResponse {
  items: Deficiency[]
  total: number
  skip: number
  limit: number
}

// ── RemediationPlan ─────────────────────────────────────────

export type RemediationStatus = 'planned' | 'in_progress' | 'completed' | 'approved'
export type RemediationPriority = 'High' | 'Medium' | 'Low'

export interface RemediationPlan {
  id: string
  deficiency_id: string
  owner_id: string
  target_date: string
  action_plan: string
  improvement_description: string | null
  priority: RemediationPriority
  owner_opinion: string | null
  reviewer_opinion: string | null
  status: RemediationStatus
  approved_by_id: string | null
  approved_at: string | null
  created_at: string
  updated_at: string
}

export interface RemediationPlanCreatePayload {
  deficiency_id: string
  owner_id: string
  target_date: string
  action_plan: string
  improvement_description?: string | null
  priority?: RemediationPriority
  owner_opinion?: string | null
  reviewer_opinion?: string | null
}

export interface RemediationPlanUpdatePayload {
  target_date?: string
  action_plan?: string
  improvement_description?: string | null
  priority?: RemediationPriority
  owner_opinion?: string | null
  reviewer_opinion?: string | null
}

export interface RemediationPlanListResponse {
  items: RemediationPlan[]
  total: number
  skip: number
  limit: number
}

export interface RemediationTransitionRequest {
  to_status: 'in_progress' | 'completed' | 'approved'
  reason?: string | null
}

export interface RemediationStatusHistory {
  id: string
  remediation_plan_id: string
  from_status: RemediationStatus | null
  to_status: RemediationStatus
  changed_by: { id: string; display_name: string }
  changed_by_id: string
  changed_at: string
  reason: string | null
}

// ── Label / Badge 상수 ──────────────────────────────────────

export const SEVERITY_LABELS: Record<DeficiencySeverity, string> = {
  low: '낮음',
  medium: '중간',
  high: '높음',
}

export const SEVERITY_BADGE_CLASS: Record<DeficiencySeverity, string> = {
  low: 'bg-green-100 text-green-700 border-green-200',
  medium: 'bg-yellow-100 text-yellow-700 border-yellow-200',
  high: 'bg-red-100 text-red-700 border-red-200',
}

export const DEFICIENCY_STATUS_LABELS: Record<DeficiencyStatus, string> = {
  open: '미해결',
  in_progress: '처리중',
  closed: '종결',
}

export const DEFICIENCY_STATUS_BADGE_CLASS: Record<DeficiencyStatus, string> = {
  open: 'bg-red-100 text-red-700 border-red-200',
  in_progress: 'bg-blue-100 text-blue-700 border-blue-200',
  closed: 'bg-gray-100 text-gray-600 border-gray-200',
}

export const REMEDIATION_STATUS_LABELS: Record<RemediationStatus, string> = {
  planned: '계획',
  in_progress: '진행중',
  completed: '완료',
  approved: '승인',
}

export const REMEDIATION_STATUS_BADGE_CLASS: Record<RemediationStatus, string> = {
  planned: 'bg-gray-100 text-gray-700 border-gray-200',
  in_progress: 'bg-blue-100 text-blue-700 border-blue-200',
  completed: 'bg-green-100 text-green-700 border-green-200',
  approved: 'bg-purple-100 text-purple-700 border-purple-200',
}

export const PRIORITY_LABELS: Record<RemediationPriority, string> = {
  High: '상',
  Medium: '중',
  Low: '하',
}

export const PRIORITY_BADGE_CLASS: Record<RemediationPriority, string> = {
  High: 'bg-red-100 text-red-700 border-red-200',
  Medium: 'bg-yellow-100 text-yellow-700 border-yellow-200',
  Low: 'bg-green-100 text-green-700 border-green-200',
}
