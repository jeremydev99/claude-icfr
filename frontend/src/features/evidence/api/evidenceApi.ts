import apiClient from '@/lib/axios'
import type {
  EvidenceFile,
  EvidenceFileListResponse,
  EvidenceFileSearchParams,
  EvidenceLink,
  EvidenceUploadPayload,
  CycleTarget,
  EvidenceLinkSearchParams,
} from '../types'

export async function fetchEvidenceFiles(params: EvidenceFileSearchParams = {}): Promise<EvidenceFileListResponse> {
  const res = await apiClient.get<EvidenceFileListResponse>('/api/evidence/files', { params })
  return res.data
}

export async function uploadEvidenceFile({ file, cycleId, controlId }: EvidenceUploadPayload): Promise<EvidenceFile> {
  // cycle_id·control_id 는 서버 필수(ADR-0032 §2.7) — 증빙은 통제 × 회차에 붙는다
  const formData = new FormData()
  formData.append('cycle_id', cycleId)
  formData.append('control_id', controlId)
  formData.append('file', file)
  const res = await apiClient.post<EvidenceFile>('/api/evidence/files', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return res.data
}

export async function downloadEvidenceFile(id: string): Promise<Blob> {
  const res = await apiClient.get<Blob>(`/api/evidence/files/${id}/download`, {
    responseType: 'blob',
  })
  return res.data
}

export async function deleteEvidenceFile(id: string): Promise<void> {
  await apiClient.delete(`/api/evidence/files/${id}`)
}

export async function fetchEvidenceLinks(params: EvidenceLinkSearchParams = {}): Promise<EvidenceLink[]> {
  const res = await apiClient.get<EvidenceLink[]>('/api/evidence/links', { params })
  return res.data
}

export async function fetchCycleTargets(cycleId: string): Promise<CycleTarget[]> {
  const res = await apiClient.get<{ items: CycleTarget[] }>(`/api/assessment/cycles/${cycleId}/targets`)
  return res.data.items
}
