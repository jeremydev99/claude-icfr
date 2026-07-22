// ADR-0027 2-B 착륙 지점. process/sub_process/risk/control 4계층 공통.
// 실 API는 아직 envelope를 보내지 않는다(2-A-3 조회 전환 전) — 전 필드 optional, 부재 시 undefined.
export interface SourceEnvelope {
  id: string
  source: 'baseline' | 'tenant'
  baseline_id: string | null
  is_overridden: boolean
}

export function isBaseline(envelope: SourceEnvelope | undefined): boolean {
  return envelope?.source === 'baseline'
}

export function isTenantAdd(envelope: SourceEnvelope | undefined): boolean {
  return envelope?.source === 'tenant'
}

// baseline 유래 → exclude(hide), tenant add → soft delete. envelope 부재(미전환 API) 시 기존 동작인 soft_delete로 폴백.
export function resolveDeleteSemantics(envelope: SourceEnvelope | undefined): 'exclude' | 'soft_delete' {
  if (isBaseline(envelope)) return 'exclude'
  return 'soft_delete'
}
