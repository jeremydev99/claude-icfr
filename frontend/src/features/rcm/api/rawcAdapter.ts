// ADR-0027 2-B 착륙 지점.
// baseline/tenant 출처 판별 필드는 2-B 스펙 확정 후 이 파일에서 흡수한다.
import type { ControlRiskAssessment } from '../types'
import type { ControlRiskAssessmentDto, RawcListResponseDto } from './dto'

export function toRawc(dto: ControlRiskAssessmentDto): ControlRiskAssessment {
  return {
    id: dto.id,
    control_id: dto.control_id,
    fiscal_year: dto.fiscal_year,
    frequency_score: dto.frequency_score,
    nature_score: dto.nature_score,
    precision_score: dto.precision_score,
    dependency_score: dto.dependency_score,
    automation_score: dto.automation_score,
    authority_score: dto.authority_score,
    review_score: dto.review_score,
    prior_year_effectiveness: dto.prior_year_effectiveness,
    overall_assessment: dto.overall_assessment,
    assessor_id: dto.assessor_id,
    assessment_date: dto.assessment_date,
    created_at: dto.created_at,
    updated_at: dto.updated_at,
  }
}

export function toRawcList(dto: RawcListResponseDto): { items: ControlRiskAssessment[]; total: number } {
  return {
    items: dto.items.map(toRawc),
    total: dto.total,
  }
}
