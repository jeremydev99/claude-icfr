import { useQuery } from '@tanstack/react-query'
import { fetchControls } from '@/features/rcm/api/controlsApi'
import { toControlList } from '@/features/rcm/api/controlsAdapter'
import type { ControlSearchParams } from '@/features/rcm/types'
import { queryKeys } from '@/lib/queryKeys'
import { useActiveTenantId } from '@/features/auth/store'

/**
 * 펼친 묶음의 통제 목록. **펼치기 전에는 부르지 않는다**(`enabled`).
 *
 * 집계는 `/api/rcm/summary` 가 내고, 목록은 기존 검색 API 를 그대로 쓴다 —
 * 같은 필터를 두 곳에서 구현하지 않기 위해서다. RCM 어댑터를 거치므로
 * 응답 형식이 바뀌어도 이 화면은 따라 바뀌지 않는다.
 */
export function useDrilldownControls(param: string | null, value: string, enabled: boolean) {
  const tenantId = useActiveTenantId()
  const params: ControlSearchParams = param
    ? ({ [param]: value, limit: 100, sort_by: 'code', sort_order: 'asc' } as ControlSearchParams)
    : {}
  return useQuery({
    queryKey: queryKeys.rcm.controls(tenantId, params),
    queryFn: () => fetchControls(params),
    select: toControlList,
    enabled: enabled && Boolean(param),
    staleTime: 1000 * 30,
  })
}
