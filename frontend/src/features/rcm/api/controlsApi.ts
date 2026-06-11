import apiClient from '@/lib/axios'
import type { ControlListResponse, ControlSearchParams } from '../types'

export async function fetchControls(
  params: ControlSearchParams
): Promise<ControlListResponse> {
  const cleanParams: Record<string, unknown> = {}
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== '') {
      cleanParams[key] = value
    }
  }
  const res = await apiClient.get<ControlListResponse>(
    '/api/rcm/controls/search',
    { params: cleanParams }
  )
  return res.data
}
