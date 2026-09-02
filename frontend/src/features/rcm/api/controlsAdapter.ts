// ADR-0027 2-B 착륙 지점.
// source envelope 규약 확정 + 2-A-3 조회 전환 완료 — 백엔드(control_resolver.py)는 source/baseline_id/
// is_overridden을 flat 필드로 응답에 얹는다. 이 어댑터가 flat DTO 필드를 도메인 SourceEnvelope(nested)로
// 조립한다. 2-A-4-3으로 process/sub_process/risk 조회도 resolver 경유로 전환되어 envelope가 항상 채워지므로,
// control과 동일하게 전 계층 required(buildSourceEnvelope, 부재 시 명시적 실패)로 통일한다.
import type { Control, ControlListResponse, ProcessItem, SubProcessItem, RiskItem } from '../types'
import type {
  ControlDto,
  ControlListResponseDto,
  ProcessItemDto,
  SubProcessItemDto,
  RiskItemDto,
} from './dto'
import { buildSourceEnvelope } from './sourceEnvelope'

export function toControl(dto: ControlDto): Control {
  return {
    id: dto.id,
    code: dto.code,
    name: dto.name,
    description: dto.description,
    objective: dto.objective,
    owner_name: dto.owner_name,
    risk_id: dto.risk_id,
    is_key_control: dto.is_key_control,
    preventive_detective: dto.preventive_detective,
    auto_manual: dto.auto_manual,
    frequency: dto.frequency,
    ipe_relevant: dto.ipe_relevant,
    activity_approval: dto.activity_approval,
    activity_verification: dto.activity_verification,
    activity_physical: dto.activity_physical,
    activity_master_data: dto.activity_master_data,
    activity_reconciliation: dto.activity_reconciliation,
    activity_supervision: dto.activity_supervision,
    related_accounts: dto.related_accounts,
    related_systems: dto.related_systems,
    euc_description: dto.euc_description,
    assertions: dto.assertions,
    process_code: dto.process_code,
    sub_process_code: dto.sub_process_code,
    risk_level: dto.risk_level,
    created_at: dto.created_at,
    envelope: buildSourceEnvelope(dto),
  }
}

export function toControlList(dto: ControlListResponseDto): ControlListResponse {
  return {
    items: dto.items.map(toControl),
    total: dto.total,
    skip: dto.skip,
    limit: dto.limit,
    sort: dto.sort,
  }
}

export function toProcessItems(dto: { items: ProcessItemDto[] }): { items: ProcessItem[] } {
  return {
    items: dto.items.map((item) => ({
      id: item.id,
      code: item.code,
      name: item.name,
      envelope: buildSourceEnvelope(item),
    })),
  }
}

export function toSubProcessItems(dto: { items: SubProcessItemDto[] }): { items: SubProcessItem[] } {
  return {
    items: dto.items.map((item) => ({
      id: item.id,
      code: item.code,
      name: item.name,
      process_id: item.process_id,
      envelope: buildSourceEnvelope(item),
    })),
  }
}

export function toRiskItems(dto: { items: RiskItemDto[] }): { items: RiskItem[] } {
  return {
    items: dto.items.map((item) => ({
      id: item.id,
      code: item.code,
      description: item.description,
      assessment_level: item.assessment_level,
      sub_process_id: item.sub_process_id,
      envelope: buildSourceEnvelope(item),
    })),
  }
}
