// 상위 3계층(Process/SubProcess/Risk) CRUD — controlsApi.ts의 통제 CRUD와 동일 패턴 미러링.
import apiClient from '@/lib/axios'
import type {
  ProcessCreatePayload,
  ProcessUpdatePayload,
  SubProcessCreatePayload,
  SubProcessUpdatePayload,
  RiskCreatePayload,
  RiskUpdatePayload,
} from '../types'
import type { ProcessItemDto, SubProcessItemDto, RiskItemDto } from './dto'
// 목록 조회는 controlsApi.ts의 기존 fetcher를 그대로 재사용한다(필터 드롭다운 소비처와 캐시 공유 — queryKey 동일).
export { fetchProcesses as fetchProcessList } from './controlsApi'

// ── Process ────────────────────────────────────────────────

export async function createProcess(payload: ProcessCreatePayload): Promise<ProcessItemDto> {
  const res = await apiClient.post<ProcessItemDto>('/api/rcm/processes', payload)
  return res.data
}

export async function updateProcessById(id: string, payload: ProcessUpdatePayload): Promise<ProcessItemDto> {
  const res = await apiClient.patch<ProcessItemDto>(`/api/rcm/processes/${id}`, payload)
  return res.data
}

export async function deleteProcess(id: string): Promise<void> {
  await apiClient.delete(`/api/rcm/processes/${id}`)
}

// ── SubProcess ─────────────────────────────────────────────

export async function fetchSubProcessList(): Promise<{ items: SubProcessItemDto[] }> {
  const res = await apiClient.get<{ items: SubProcessItemDto[] }>('/api/rcm/sub-processes', {
    params: { limit: 200 },
  })
  return res.data
}

export async function createSubProcess(payload: SubProcessCreatePayload): Promise<SubProcessItemDto> {
  const res = await apiClient.post<SubProcessItemDto>('/api/rcm/sub-processes', payload)
  return res.data
}

export async function updateSubProcessById(id: string, payload: SubProcessUpdatePayload): Promise<SubProcessItemDto> {
  const res = await apiClient.patch<SubProcessItemDto>(`/api/rcm/sub-processes/${id}`, payload)
  return res.data
}

export async function deleteSubProcess(id: string): Promise<void> {
  await apiClient.delete(`/api/rcm/sub-processes/${id}`)
}

// ── Risk ───────────────────────────────────────────────────

export async function fetchRiskList(): Promise<{ items: RiskItemDto[] }> {
  const res = await apiClient.get<{ items: RiskItemDto[] }>('/api/rcm/risks', {
    params: { limit: 200 },
  })
  return res.data
}

export async function createRisk(payload: RiskCreatePayload): Promise<RiskItemDto> {
  const res = await apiClient.post<RiskItemDto>('/api/rcm/risks', payload)
  return res.data
}

export async function updateRiskById(id: string, payload: RiskUpdatePayload): Promise<RiskItemDto> {
  const res = await apiClient.patch<RiskItemDto>(`/api/rcm/risks/${id}`, payload)
  return res.data
}

export async function deleteRisk(id: string): Promise<void> {
  await apiClient.delete(`/api/rcm/risks/${id}`)
}
