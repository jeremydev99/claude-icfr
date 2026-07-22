// ADR-0027 2-B 착륙 지점. process/sub_process/risk/control 4계층 공통.
// 실 API는 아직 envelope를 보내지 않는다(2-A-3 조회 전환 전) — 전 필드 optional, 부재 시 undefined.
//
// 계약 정합(2026-07-22): 백엔드 control_resolver.py(d325705, 2-B-4)는 source/baseline_id/is_overridden을
// resolved dict의 최상위(flat) 필드로 얹힌다 — nested envelope 객체가 아니다. id는 신규 필드가 아니라
// 기존 항목의 id 필드를 정체성 id로 그대로 덮어쓰는 방식(row["id"] = base.id 등). 따라서 DTO(wire)는
// flat 3필드(source/baseline_id/is_overridden)만 갖고, 이 도메인 SourceEnvelope(nested)는 어댑터가
// flat 필드 + 기존 id를 모아 조립한다(buildSourceEnvelope).
export interface SourceEnvelope {
  id: string
  source: 'baseline' | 'tenant'
  baseline_id: string | null
  is_overridden: boolean
}

// dto의 flat envelope 필드(source/baseline_id/is_overridden) + 기존 id로 도메인 SourceEnvelope를 조립.
// source가 없으면(현재 미전환 API) undefined로 폴백 — throw 없음.
export function buildSourceEnvelope(dto: {
  id: string
  source?: SourceEnvelope['source']
  baseline_id?: string | null
  is_overridden?: boolean
}): SourceEnvelope | undefined {
  if (dto.source === undefined) return undefined
  return {
    id: dto.id,
    source: dto.source,
    baseline_id: dto.baseline_id ?? null,
    is_overridden: dto.is_overridden ?? false,
  }
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
