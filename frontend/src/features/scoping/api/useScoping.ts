import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import apiClient from '@/lib/axios'
import { queryKeys } from '@/lib/queryKeys'
import { useActiveTenantId } from '@/features/auth/store'
import type { ScopingDetail, ScopingListItem, ScopingMeta, ScopingSummary } from '../types'

export function useScopingMeta() {
  const tenantId = useActiveTenantId()
  return useQuery({
    queryKey: queryKeys.scoping.meta(tenantId),
    queryFn: async () => (await apiClient.get<ScopingMeta>('/api/scoping/meta')).data,
    staleTime: 5 * 60_000,
  })
}

export function useScopingList() {
  const tenantId = useActiveTenantId()
  return useQuery({
    queryKey: queryKeys.scoping.list(tenantId),
    queryFn: async () => (await apiClient.get<ScopingListItem[]>('/api/scoping')).data,
  })
}

export function useScopingDetail(id: string | null) {
  const tenantId = useActiveTenantId()
  return useQuery({
    queryKey: queryKeys.scoping.detail(tenantId, id),
    queryFn: async () => (await apiClient.get<ScopingDetail>(`/api/scoping/${id}`)).data,
    enabled: Boolean(id),
  })
}

export function useScopingSummary() {
  const tenantId = useActiveTenantId()
  return useQuery({
    queryKey: queryKeys.scoping.summary(tenantId),
    queryFn: async () => (await apiClient.get<ScopingSummary>('/api/scoping/summary')).data,
    staleTime: 60_000,
  })
}

/**
 * 모든 쓰기는 **갱신된 상세를 그대로 돌려받는다** — 금액 하나를 바꿔도 수행중요성·양적 판정·결론이
 * 전부 다시 산출되므로, 응답으로 상세 캐시를 통째로 바꾸고 목록·대시보드는 무효화한다.
 */
export function useScopingWrite(id: string | null) {
  const queryClient = useQueryClient()
  const tenantId = useActiveTenantId()
  return useMutation({
    mutationFn: async ({ method, path, body }: { method: 'post' | 'patch' | 'delete'; path: string; body?: unknown }) => {
      const url = `/api/scoping${path}`
      const res = method === 'delete' ? await apiClient.delete<ScopingDetail>(url)
        : method === 'post' ? await apiClient.post<ScopingDetail>(url, body)
          : await apiClient.patch<ScopingDetail>(url, body)
      return res.data
    },
    onSuccess: (detail) => {
      queryClient.setQueryData(queryKeys.scoping.detail(tenantId, detail.id ?? id), detail)
      queryClient.invalidateQueries({ queryKey: queryKeys.scoping.list(tenantId) })
      queryClient.invalidateQueries({ queryKey: queryKeys.scoping.summary(tenantId) })
    },
  })
}

export const errorDetail = (e: unknown, fallback: string) =>
  (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? fallback
