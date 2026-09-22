import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  createEucFile,
  createInfoItem,
  deleteEucFile,
  deleteInfoItem,
  fetchEucFiles,
  fetchEucMeta,
  fetchEucSummary,
  fetchInfoItems,
  updateEucFile,
  updateInfoItem,
} from './eucIucApi'
import type { EucFilePayload, InfoItemPayload } from '../types'
import { queryKeys } from '@/lib/queryKeys'
import { useActiveTenantId } from '@/features/auth/store'

export function useEucMeta() {
  const tenantId = useActiveTenantId()
  return useQuery({ queryKey: queryKeys.euc.meta(tenantId), queryFn: fetchEucMeta, staleTime: 60_000 })
}

export function useEucFiles() {
  const tenantId = useActiveTenantId()
  return useQuery({ queryKey: queryKeys.euc.files(tenantId), queryFn: fetchEucFiles, staleTime: 30_000 })
}

export function useInfoItems() {
  const tenantId = useActiveTenantId()
  return useQuery({ queryKey: queryKeys.euc.items(tenantId), queryFn: fetchInfoItems, staleTime: 30_000 })
}

export function useEucSummary() {
  const tenantId = useActiveTenantId()
  return useQuery({
    queryKey: queryKeys.euc.summary(tenantId), queryFn: fetchEucSummary, staleTime: 60_000,
  })
}

/**
 * 정보 항목을 바꾸면 **파일의 산출값(중요성·위험 등급)도 바뀐다.** 한쪽만 무효화하면
 * EUC 화면이 옛 등급을 들고 있으므로 EUC·IUC·대시보드 집계를 한꺼번에 지운다.
 */
function useInvalidateAll() {
  const queryClient = useQueryClient()
  const tenantId = useActiveTenantId()
  return () => queryClient.invalidateQueries({ queryKey: queryKeys.euc.all(tenantId) })
}

export function useSaveEucFile() {
  const invalidate = useInvalidateAll()
  return useMutation({
    mutationFn: ({ id, body }: { id: string | null; body: EucFilePayload }) =>
      id ? updateEucFile(id, body) : createEucFile(body),
    onSuccess: invalidate,
  })
}

export function useDeleteEucFile() {
  const invalidate = useInvalidateAll()
  return useMutation({ mutationFn: deleteEucFile, onSuccess: invalidate })
}

export function useSaveInfoItem() {
  const invalidate = useInvalidateAll()
  return useMutation({
    mutationFn: ({ id, body }: { id: string | null; body: InfoItemPayload }) =>
      id ? updateInfoItem(id, body) : createInfoItem(body),
    onSuccess: invalidate,
  })
}

export function useDeleteInfoItem() {
  const invalidate = useInvalidateAll()
  return useMutation({ mutationFn: deleteInfoItem, onSuccess: invalidate })
}
