import apiClient from '@/lib/axios'
import type {
  EvidenceFile,
  EvidenceFileListResponse,
  EvidenceFileSearchParams,
  EvidenceLink,
  EvidenceLinkSearchParams,
} from '../types'

export async function fetchEvidenceFiles(params: EvidenceFileSearchParams = {}): Promise<EvidenceFileListResponse> {
  const res = await apiClient.get<EvidenceFileListResponse>('/api/evidence/files', { params })
  return res.data
}

export async function uploadEvidenceFile(file: File): Promise<EvidenceFile> {
  const formData = new FormData()
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
