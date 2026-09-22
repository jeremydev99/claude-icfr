import apiClient from '@/lib/axios'
import type {
  EucFile,
  EucFileList,
  EucFilePayload,
  EucIucSummary,
  EucMeta,
  InfoItem,
  InfoItemList,
  InfoItemPayload,
} from '../types'

export const fetchEucMeta = async () => (await apiClient.get<EucMeta>('/api/euc/meta')).data
export const fetchEucFiles = async () => (await apiClient.get<EucFileList>('/api/euc/files')).data
export const fetchEucSummary = async () =>
  (await apiClient.get<EucIucSummary>('/api/euc/summary')).data

export const createEucFile = async (body: EucFilePayload) =>
  (await apiClient.post<EucFile>('/api/euc/files', body)).data
export const updateEucFile = async (id: string, body: EucFilePayload) =>
  (await apiClient.patch<EucFile>(`/api/euc/files/${id}`, body)).data
export const deleteEucFile = async (id: string) => {
  await apiClient.delete(`/api/euc/files/${id}`)
}

export const fetchInfoItems = async () =>
  (await apiClient.get<InfoItemList>('/api/iuc/items')).data
export const createInfoItem = async (body: InfoItemPayload) =>
  (await apiClient.post<InfoItem>('/api/iuc/items', body)).data
export const updateInfoItem = async (id: string, body: InfoItemPayload) =>
  (await apiClient.patch<InfoItem>(`/api/iuc/items/${id}`, body)).data
export const deleteInfoItem = async (id: string) => {
  await apiClient.delete(`/api/iuc/items/${id}`)
}
