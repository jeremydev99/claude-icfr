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
  assertions: AssertionCode[] | null
  process_code: string | null
  sub_process_code: string | null
  risk_level: RiskLevel | null
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
  sort_by?: 'code' | 'name' | 'frequency' | 'created_at' | 'owner_name'
  sort_order?: 'asc' | 'desc'
}

export interface ControlListResponse {
  items: Control[]
  total: number
  skip: number
  limit: number
  sort?: string
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

export interface ProcessItem {
  id: string
  code: string
  name: string
}

export interface SubProcessItem {
  id: string
  code: string
  name: string
  process_id: string
}

export interface RiskItem {
  id: string
  code: string
  description: string
  assessment_level: RiskLevel
  sub_process_id: string
}

// ── RAWC (ControlRiskAssessment) ──────────────────────────

export type PriorYearEffectiveness = 'Effective' | 'Not_Effective' | 'N/A'
export type OverallAssessment = 'Not_Higher' | 'Higher'

export interface ControlRiskAssessment {
  id: string
  control_id: string
  fiscal_year: number
  frequency_score: number
  nature_score: number
  precision_score: number
  dependency_score: number
  automation_score: number
  authority_score: number
  review_score: number
  prior_year_effectiveness: PriorYearEffectiveness
  overall_assessment: OverallAssessment
  assessor_id: string | null
  assessment_date: string | null
  created_at: string
  updated_at: string
}

export interface RawcCreatePayload {
  control_id: string
  fiscal_year: number
  frequency_score?: number
  nature_score?: number
  precision_score?: number
  dependency_score?: number
  automation_score?: number
  authority_score?: number
  review_score?: number
  prior_year_effectiveness?: PriorYearEffectiveness
  overall_assessment?: OverallAssessment
  assessor_id?: string | null
  assessment_date?: string | null
}

export type RawcUpdatePayload = Partial<Omit<RawcCreatePayload, 'control_id' | 'fiscal_year'>>

export const RAWC_SCORE_FIELDS = [
  { key: 'frequency_score', label: '빈도' },
  { key: 'nature_score', label: '성격' },
  { key: 'precision_score', label: '정밀도' },
  { key: 'dependency_score', label: '의존성' },
  { key: 'automation_score', label: '자동화' },
  { key: 'authority_score', label: '권한' },
  { key: 'review_score', label: '검토' },
] as const

export const PRIOR_YEAR_LABELS: Record<PriorYearEffectiveness, string> = {
  'Effective': '유효',
  'Not_Effective': '비유효',
  'N/A': '해당없음',
}

export const OVERALL_ASSESSMENT_LABELS: Record<OverallAssessment, string> = {
  'Not_Higher': '높지 않음',
  'Higher': '높음',
}

// POST /controls 요청 페이로드 (서버 생성 필드 + JOIN 표시 필드 제외)
export type ControlCreatePayload = Omit<Control,
  | 'id' | 'created_at' | 'updated_at'
  | 'process_code' | 'sub_process_code' | 'risk_level' | 'assertions'
>

// PATCH /controls/{id} 요청 페이로드 (code·risk_id 불변 필드 제외, 전부 옵셔널)
export type ControlUpdatePayload = Partial<Omit<ControlCreatePayload, 'code' | 'risk_id'>>
