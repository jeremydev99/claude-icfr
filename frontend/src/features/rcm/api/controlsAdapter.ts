// ADR-0027 2-B 착륙 지점.
// source envelope 규약 확정(2-A-3 미도래) — envelope는 optional 항등 매핑만, 실 연결은 2-A-3 이후.
import type { Control, ControlListResponse, ProcessItem, SubProcessItem, RiskItem } from '../types'
import type {
  ControlDto,
  ControlListResponseDto,
  ProcessItemDto,
  SubProcessItemDto,
  RiskItemDto,
} from './dto'

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
    envelope: dto.envelope,
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
      envelope: item.envelope,
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
      envelope: item.envelope,
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
      envelope: item.envelope,
    })),
  }
}
