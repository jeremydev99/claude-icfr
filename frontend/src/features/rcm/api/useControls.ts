import { useQuery } from '@tanstack/react-query'
import { fetchControls } from './controlsApi'
import type { Control, ControlSearchParams, ControlListResponse } from '../types'

export function useControls(params: ControlSearchParams) {
  return useQuery<ControlListResponse>({
    queryKey: ['controls', params],
    queryFn: () => fetchControls(params),
    placeholderData: (previous) => previous,
    staleTime: 1000 * 30,
  })
}

// TODO: ICFR_frontend_8에서 POST /api/rcm/controls 로 교체
export function addControl(payload: Omit<Control, 'id' | 'created_at'>): Control {
  console.warn('[mock] addControl — 새로고침 시 사라집니다. 다음 작업에서 실제 API로 전환됩니다.')
  return {
    ...payload,
    id: crypto.randomUUID(),
    created_at: new Date().toISOString(),
  }
}

// TODO: ICFR_frontend_8에서 PATCH /api/rcm/controls/{id} 로 교체
export function updateControl(_id: string, _payload: Partial<Control>): null {
  console.warn('[mock] updateControl — 새로고침 시 사라집니다. 다음 작업에서 실제 API로 전환됩니다.')
  return null
}
