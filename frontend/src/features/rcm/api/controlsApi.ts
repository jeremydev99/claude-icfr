import apiClient from '@/lib/axios'
import type { ControlCreatePayload, ControlUpdatePayload, ControlSearchParams } from '../types'
import type {
  ControlDto,
  ControlListResponseDto,
  ProcessItemDto,
  SubProcessItemDto,
  RiskItemDto,
} from './dto'

export async function fetchControls(params: ControlSearchParams): Promise<ControlListResponseDto> {
  const cleanParams: Record<string, unknown> = {}
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== '') {
      cleanParams[key] = value
    }
  }
  const res = await apiClient.get<ControlListResponseDto>('/api/rcm/controls/search', { params: cleanParams })
  return res.data
}

export async function fetchProcesses(): Promise<{ items: ProcessItemDto[] }> {
  const res = await apiClient.get<{ items: ProcessItemDto[] }>('/api/rcm/processes', {
    params: { limit: 100 },
  })
  return res.data
}

export async function fetchSubProcesses(processId?: string): Promise<{ items: SubProcessItemDto[] }> {
  const params: Record<string, unknown> = { limit: 200 }
  if (processId) params.process_id = processId
  const res = await apiClient.get<{ items: SubProcessItemDto[] }>('/api/rcm/sub-processes', { params })
  return res.data
}

export async function fetchRisksBySubProcessId(subProcessId: string): Promise<{ items: RiskItemDto[] }> {
  const res = await apiClient.get<{ items: RiskItemDto[] }>('/api/rcm/risks', {
    params: { sub_process_id: subProcessId, limit: 50 },
  })
  return res.data
}

export async function createControl(payload: ControlCreatePayload): Promise<ControlDto> {
  const res = await apiClient.post<ControlDto>('/api/rcm/controls', payload)
  return res.data
}

export async function updateControlById(id: string, payload: ControlUpdatePayload): Promise<ControlDto> {
  const res = await apiClient.patch<ControlDto>(`/api/rcm/controls/${id}`, payload)
  return res.data
}

export async function deleteControl(id: string): Promise<void> {
  await apiClient.delete(`/api/rcm/controls/${id}`)
}
