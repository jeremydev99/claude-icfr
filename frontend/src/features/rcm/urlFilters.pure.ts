// 대시보드 → RCM 드릴스루의 URL 필터 해석 (4-1). zustand·react 비의존 순수 함수라
// 테스트에서 그대로 부를 수 있다(`permissions.pure.ts` 와 같은 규약).
import type { ControlSearchParams } from './types'

/** 대시보드가 넘길 수 있는 필터. **목록에 없는 쿼리 파라미터는 무시한다** — 임의의 값이
 *  검색 파라미터로 그대로 흘러들면 백엔드가 모르는 키에 대해 무슨 일을 하는지 알 수 없다. */
export const URL_FILTER_KEYS = [
  'q', 'process_code', 'sub_process_code', 'risk_level', 'frequency',
  'assessment_frequency', 'ipe_relevant', 'activity', 'auto_manual',
  'preventive_detective', 'assertion', 'owner',
] as const

/**
 * URL → 초기 필터. **단방향 1회 주입이며 URL 을 되쓰지 않는다.**
 *
 * 양방향 동기화(필터를 바꿀 때마다 URL 갱신)는 하지 않는다 — 필터 조작마다 history 가
 * 쌓여 뒤로가기 동작이 달라지고, 그건 대시보드 때문에 기존 화면의 UX 를 바꾸는 것이다.
 */
export function paramsFromUrl(
  search: URLSearchParams,
  defaults: ControlSearchParams,
): ControlSearchParams {
  const parsed: Record<string, unknown> = {}
  for (const key of URL_FILTER_KEYS) {
    const value = search.get(key)
    if (value === null || value === '') continue
    parsed[key] = value
  }
  // 백엔드 집계는 파이썬 bool 을 문자열로 낸다("True"/"False") — 양쪽 표기를 모두 받는다.
  const keyControl = search.get('is_key_control')?.toLowerCase()
  if (keyControl === 'true' || keyControl === 'false') {
    parsed.is_key_control = keyControl === 'true'
  }
  return { ...defaults, ...parsed }
}
