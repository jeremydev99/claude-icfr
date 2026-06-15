import apiClient from '@/lib/axios'
import type {
  Control,
  ControlCreatePayload,
  ControlUpdatePayload,
  ControlListResponse,
  ControlSearchParams,
  ProcessItem,
  SubProcessItem,
  RiskItem,
} from '../types'

export async function fetchControls(params: ControlSearchParams): Promise<ControlListResponse> {
  const cleanParams: Record<string, unknown> = {}
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== '') {
      cleanParams[key] = value
    }
  }
  const res = await apiClient.get<ControlListResponse>('/api/rcm/controls/search', { params: cleanParams })
  return res.data
}

export async function fetchProcesses(): Promise<{ items: ProcessItem[] }> {
  const res = await apiClient.get<{ items: ProcessItem[] }>('/api/rcm/processes', {
    params: { limit: 100 },
  })
  return res.data
}

export async function fetchSubProcesses(processId?: string): Promise<{ items: SubProcessItem[] }> {
  const params: Record<string, unknown> = { limit: 200 }
  if (processId) params.process_id = processId
  const res = await apiClient.get<{ items: SubProcessItem[] }>('/api/rcm/sub-processes', { params })
  return res.data
}

export async function fetchRisksBySubProcessId(subProcessId: string): Promise<{ items: RiskItem[] }> {
  const res = await apiClient.get<{ items: RiskItem[] }>('/api/rcm/risks', {
    params: { sub_process_id: subProcessId, limit: 50 },
  })
  return res.data
}

export async function createControl(payload: ControlCreatePayload): Promise<Control> {
  const res = await apiClient.post<Control>('/api/rcm/controls', payload)
  return res.data
}

export async function updateControlById(id: string, payload: ControlUpdatePayload): Promise<Control> {
  const res = await apiClient.patch<Control>(`/api/rcm/controls/${id}`, payload)
  return res.data
}

export async function deleteControl(id: string): Promise<void> {
  await apiClient.delete(`/api/rcm/controls/${id}`)
}
