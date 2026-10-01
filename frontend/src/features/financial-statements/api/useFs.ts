import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import apiClient from '@/lib/axios'
import { queryKeys } from '@/lib/queryKeys'
import { useActiveTenantId } from '@/features/auth/store'
import type { FsMeta, StatementDetail, StatementListItem, SuspenseAction, SuspenseItem, ValidationResult } from '../types'

export function useFsMeta() {
  const tenantId = useActiveTenantId()
  return useQuery({
    queryKey: queryKeys.fs.meta(tenantId),
    queryFn: async () => (await apiClient.get<FsMeta>('/api/fs/meta')).data,
    staleTime: 5 * 60_000,
  })
}

export function useFsStatements() {
  const tenantId = useActiveTenantId()
  return useQuery({
    queryKey: queryKeys.fs.list(tenantId),
    queryFn: async () => (await apiClient.get<StatementListItem[]>('/api/fs/statements')).data,
  })
}

export function useFsStatement(id: string | null) {
  const tenantId = useActiveTenantId()
  return useQuery({
    queryKey: queryKeys.fs.detail(tenantId, id),
    queryFn: async () => (await apiClient.get<StatementDetail>(`/api/fs/statements/${id}`)).data,
    enabled: Boolean(id),
  })
}

export function useFsSuspense(id: string | null) {
  const tenantId = useActiveTenantId()
  return useQuery({
    queryKey: queryKeys.fs.suspense(tenantId, id),
    queryFn: async () => (await apiClient.get<SuspenseItem[]>(`/api/fs/statements/${id}/suspense`)).data,
    enabled: Boolean(id),
  })
}

export type FsWrite =
  | { kind: 'finalize'; reason?: string }
  | { kind: 'reopen'; reason: string }
  | { kind: 'tolerance'; tolerance: string }
  | { kind: 'resolve'; amountId: string; action: SuspenseAction; reason: string; targetAccountId?: string }

/**
 * 모든 쓰기는 **갱신된 상세를 돌려받는다**(검증 결과 포함) — 응답으로 상세 캐시를 바꾸고
 * 목록·임시계정 목록은 무효화한다. 확정 실패(422)는 `detail.validation` 에 항목별 오류가 온다.
 */
export function useFsWrite(id: string | null) {
  const queryClient = useQueryClient()
  const tenantId = useActiveTenantId()
  return useMutation({
    mutationFn: async (w: FsWrite) => {
      const base = `/api/fs/statements/${id}`
      switch (w.kind) {
        case 'finalize':
          return (await apiClient.post<StatementDetail>(`${base}/finalize`, { reason: w.reason ?? null })).data
        case 'reopen':
          return (await apiClient.post<StatementDetail>(`${base}/reopen`, { reason: w.reason })).data
        case 'tolerance':
          return (await apiClient.patch<StatementDetail>(base, { tolerance: w.tolerance })).data
        case 'resolve':
          return (await apiClient.post<StatementDetail>(`${base}/suspense/${w.amountId}/resolve`, {
            action: w.action, reason: w.reason, target_account_id: w.targetAccountId ?? null,
          })).data
      }
    },
    onSuccess: (detail) => {
      queryClient.setQueryData(queryKeys.fs.detail(tenantId, detail.id), detail)
      queryClient.invalidateQueries({ queryKey: queryKeys.fs.list(tenantId) })
      queryClient.invalidateQueries({ queryKey: queryKeys.fs.suspense(tenantId, detail.id) })
    },
  })
}

type ErrorBody = { response?: { data?: { detail?: string | { message?: string; validation?: ValidationResult } } } }

/** 오류 메시지 — 확정 실패 422 는 `{message, validation}` 객체로 온다 */
export function errorDetail(e: unknown, fallback: string): string {
  const d = (e as ErrorBody)?.response?.data?.detail
  if (typeof d === 'string') return d
  if (d && typeof d === 'object' && d.message) return d.message
  return fallback
}

export function errorValidation(e: unknown): ValidationResult | null {
  const d = (e as ErrorBody)?.response?.data?.detail
  return d && typeof d === 'object' && d.validation ? d.validation : null
}
