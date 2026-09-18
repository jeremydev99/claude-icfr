import apiClient from '@/lib/axios'
import type { RcmSummary } from './types'

export async function fetchRcmSummary(): Promise<RcmSummary> {
  const res = await apiClient.get<RcmSummary>('/api/rcm/summary')
  return res.data
}
