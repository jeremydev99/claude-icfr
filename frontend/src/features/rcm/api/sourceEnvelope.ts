// ADR-0027 2-B 착륙 지점. process/sub_process/risk/control 4계층 공통 타입.
//
// 계약 정합(2026-07-22): 백엔드 control_resolver.py(d325705, 2-B-4)는 source/baseline_id/is_overridden을
// resolved dict의 최상위(flat) 필드로 얹힌다 — nested envelope 객체가 아니다. id는 신규 필드가 아니라
// 기존 항목의 id 필드를 정체성 id로 그대로 덮어쓰는 방식(row["id"] = base.id 등). 따라서 DTO(wire)는
// flat 3필드(source/baseline_id/is_overridden)만 갖고, 이 도메인 SourceEnvelope(nested)는 어댑터가
// flat 필드 + 기존 id를 모아 조립한다.
//
// required 전환(2026-07-24, 2-A-3 조회 전환 착륙): control 검색(`/controls/search`)·상세(`/controls/{id}`)만
// resolve_controls 경유로 전환되어 envelope 필드가 항상 채워진다. process/sub_process/risk 목록 API는
// 아직 legacy 평문 조회(resolve_processes 등은 존재하나 라우터 미연결)라 envelope를 보내지 않는다 —
// 이 3계층은 부재가 계약 위반이 아니라 "아직 미전환" 정상 상태이므로 optional 폴백을 유지한다.
export interface SourceEnvelope {
  id: string
  source: 'baseline' | 'tenant'
  baseline_id: string | null
  is_overridden: boolean
}

// control 전용 — 2-A-3 전환 이후 필드 부재는 계약 위반. 조용히 넘기지 않고 명시적으로 실패시킨다.
export function buildSourceEnvelope(dto: {
  id: string
  source: SourceEnvelope['source']
  baseline_id: string | null
  is_overridden: boolean
}): SourceEnvelope {
  const missing = (['source', 'is_overridden', 'baseline_id'] as const).filter(
    (key) => dto[key] === undefined,
  )
  if (missing.length > 0) {
    const message = `[RCM envelope] 계약 위반: ${missing.join(', ')} 필드 누락 (control id=${dto.id})`
    if (import.meta.env.DEV) {
      throw new Error(message)
    }
    // 프로덕션은 화면 전체 크래시를 막기 위해 안전한 최소값으로 렌더 — 콘솔 에러는 1회만 남긴다.
    console.error(message)
    return { id: dto.id, source: 'tenant', baseline_id: null, is_overridden: false }
  }
  return {
    id: dto.id,
    source: dto.source,
    baseline_id: dto.baseline_id,
    is_overridden: dto.is_overridden,
  }
}

// process/sub_process/risk 전용 — 해당 목록 API는 아직 2-A-3 전환 전이라 envelope 필드가 원래 없다.
// 부재는 정상이므로 조용한 undefined 폴백을 유지한다(throw 없음).
export function buildOptionalSourceEnvelope(dto: {
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
