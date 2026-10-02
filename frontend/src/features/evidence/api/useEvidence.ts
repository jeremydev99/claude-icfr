import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { fetchEvidenceFiles, uploadEvidenceFile, deleteEvidenceFile, fetchCycleTargets } from './evidenceApi'
import type { EvidenceFileSearchParams } from '../types'
import { queryKeys } from '@/lib/queryKeys'
import { useActiveTenantId } from '@/features/auth/store'
import { resolveEvidenceError as resolveUploadError } from '../evidence.pure'

export function useEvidenceFiles(params: EvidenceFileSearchParams = {}) {
  const tenantId = useActiveTenantId()
  return useQuery({
    queryKey: queryKeys.evidence.files(tenantId, params),
    queryFn: () => fetchEvidenceFiles(params),
    placeholderData: (previous) => previous,
    staleTime: 1000 * 30,
  })
}

export function useUploadEvidenceFile() {
  const queryClient = useQueryClient()
  const tenantId = useActiveTenantId()
  return useMutation({
    mutationFn: uploadEvidenceFile,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.evidence.filesAll(tenantId) })
    },
    meta: { resolveUploadError },
  })
}

export function useDeleteEvidenceFile() {
  const queryClient = useQueryClient()
  const tenantId = useActiveTenantId()
  return useMutation({
    mutationFn: deleteEvidenceFile,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.evidence.filesAll(tenantId) })
    },
  })
}

/** 회차 대상 통제 스냅샷 — 업로드 시 통제 선택지. 회차 미선택이면 조회하지 않는다. */
export function useCycleTargets(cycleId: string | null) {
  const tenantId = useActiveTenantId()
  return useQuery({
    queryKey: queryKeys.evidence.cycleTargets(tenantId, cycleId),
    queryFn: () => fetchCycleTargets(cycleId as string),
    enabled: !!cycleId,
    staleTime: 5 * 60_000,
  })
}
