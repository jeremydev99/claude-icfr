// 서버 응답 원형(wire format). 백엔드 계약 변경 시 여기만 바뀐다.
import type {
  PreventiveDetective,
  AutoManual,
  Frequency,
  AssertionCode,
  RiskLevel,
  PriorYearEffectiveness,
  OverallAssessment,
} from '../types'
import type { SourceEnvelope } from './sourceEnvelope'

export interface ControlDto {
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
  envelope?: SourceEnvelope
}

export interface ControlListResponseDto {
  items: ControlDto[]
  total: number
  skip: number
  limit: number
  sort?: string
}

export interface ProcessItemDto {
  id: string
  code: string
  name: string
  envelope?: SourceEnvelope
}

export interface SubProcessItemDto {
  id: string
  code: string
  name: string
  process_id: string
  envelope?: SourceEnvelope
}

export interface RiskItemDto {
  id: string
  code: string
  description: string
  assessment_level: RiskLevel
  sub_process_id: string
  envelope?: SourceEnvelope
}

// ── RAWC (ControlRiskAssessment) ──────────────────────────

export interface ControlRiskAssessmentDto {
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

export interface RawcListResponseDto {
  items: ControlRiskAssessmentDto[]
  total: number
}
