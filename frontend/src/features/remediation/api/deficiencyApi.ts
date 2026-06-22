import apiClient from '@/lib/axios'
import type {
  Deficiency,
  DeficiencyCreatePayload,
  DeficiencyListResponse,
  DeficiencyUpdatePayload,
} from '../types'

export async function fetchDeficiencies(params: { skip?: number; limit?: number }): Promise<DeficiencyListResponse> {
  const res = await apiClient.get<DeficiencyListResponse>('/api/remediation/deficiencies', { params })
  return res.data
}

export async function createDeficiency(payload: DeficiencyCreatePayload): Promise<Deficiency> {
  const res = await apiClient.post<Deficiency>('/api/remediation/deficiencies', payload)
  return res.data
}

export async function fetchDeficiencyDetail(id: string): Promise<Deficiency> {
  const res = await apiClient.get<Deficiency>(`/api/remediation/deficiencies/${id}`)
  return res.data
}

export async function updateDeficiency({ id, payload }: { id: string; payload: DeficiencyUpdatePayload }): Promise<Deficiency> {
  const res = await apiClient.patch<Deficiency>(`/api/remediation/deficiencies/${id}`, payload)
  return res.data
}

export async function deleteDeficiency(id: string): Promise<void> {
  await apiClient.delete(`/api/remediation/deficiencies/${id}`)
}
