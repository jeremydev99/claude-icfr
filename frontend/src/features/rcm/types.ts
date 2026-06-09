export type AssertionCode = 'E' | 'C' | 'R' | 'V' | 'P' | 'O' | 'M'
export type RiskLevel = 'LR' | 'MR' | 'HR' | 'SR'
export type Frequency = 'O' | 'D' | 'W' | 'M' | 'Q' | 'A'
export type PreventiveDetective = 'P' | 'D'
export type AutoManual = 'A' | 'M' | 'IT'

export interface Control {
  id: string
  code: string
  name: string
  description: string | null
  objective: string | null
  owner_name: string | null
  risk_id: string
  is_key_control: boolean
  preventive_detective: PreventiveDetective
  auto_manual: AutoManual
  frequency: Frequency
  ipe_relevant: 'Y' | 'N' | 'N/A'
  activity_approval: boolean
  activity_verification: boolean
  activity_physical: boolean
  activity_master_data: boolean
  activity_reconciliation: boolean
  activity_supervision: boolean
  related_accounts: string | null
  related_systems: string | null
  euc_description: string | null
  assertions: AssertionCode[]
  process_code: string
  sub_process_code: string
  risk_level: RiskLevel
  created_at: string
}

export interface ControlSearchParams {
  q?: string
  process_code?: string
  sub_process_code?: string
  risk_level?: RiskLevel
  frequency?: Frequency
  is_key_control?: boolean
  auto_manual?: AutoManual
  preventive_detective?: PreventiveDetective
  assertion?: AssertionCode
  owner?: string
  skip?: number
  limit?: number
  sort_by?: 'code' | 'name' | 'frequency' | 'created_at'
  sort_order?: 'asc' | 'desc'
}

export interface ControlListResponse {
  items: Control[]
  total: number
  skip: number
  limit: number
}

export const RISK_LEVEL_LABELS: Record<RiskLevel, string> = {
  LR: '낮음',
  MR: '보통',
  HR: '높음',
  SR: '유의',
}

export const FREQUENCY_LABELS: Record<Frequency, string> = {
  O: '수시',
  D: '일',
  W: '주',
  M: '월',
  Q: '분기',
  A: '연',
}

export const AUTO_MANUAL_LABELS: Record<AutoManual, string> = {
  A: '자동',
  M: '수동',
  IT: 'IT의존수동',
}

export const PD_LABELS: Record<PreventiveDetective, string> = {
  P: '예방',
  D: '적발',
}

export const ASSERTION_LABELS: Record<AssertionCode, string> = {
  E: '실재성',
  C: '완전성',
  R: '권리와의무',
  V: '평가',
  P: '표시와공시',
  O: '발생',
  M: '기타',
}
