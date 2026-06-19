import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import axios from 'axios'
import { fetchEvidenceFiles, uploadEvidenceFile, deleteEvidenceFile } from './evidenceApi'
import type { EvidenceFileSearchParams } from '../types'

function resolveUploadError(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const status = error.response?.status
    if (status === 413) return '파일 크기가 서버 허용 한도를 초과했습니다.'
    if (status === 415) return '허용되지 않는 파일 형식입니다.'
  }
  return '업로드 중 오류가 발생했습니다.'
}

export function useEvidenceFiles(params: EvidenceFileSearchParams = {}) {
  return useQuery({
    queryKey: ['evidence-files', params],
    queryFn: () => fetchEvidenceFiles(params),
    placeholderData: (previous) => previous,
    staleTime: 1000 * 30,
  })
}

export function useUploadEvidenceFile() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: uploadEvidenceFile,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['evidence-files'] })
    },
    meta: { resolveUploadError },
  })
}

export function useDeleteEvidenceFile() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: deleteEvidenceFile,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['evidence-files'] })
    },
  })
}
