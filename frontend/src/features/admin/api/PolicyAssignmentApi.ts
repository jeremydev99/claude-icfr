import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import apiClient from '@/lib/axios'
import { useActiveTenantId } from '@/features/auth/store'
import type { TenantPolicy } from '../PolicyDefs.pure'
import type { ListResponse } from '../types'

// queryKeys.ts 는 건드리지 않는다 — 같은 모양(['tenant', seg, 'org', ...])으로 여기서 만든다.
type TenantId = string | null
const seg = (t: TenantId) => t ?? 'no-tenant'
export const orgExtraKeys = {
  policies: (t: TenantId) => ['tenant', seg(t), 'org', 'policies'] as const,
  assignments: (t: TenantId) => ['tenant', seg(t), 'org', 'assignments'] as const,
  targetProcesses: (t: TenantId) => ['tenant', seg(t), 'org', 'assign-targets', 'processes'] as const,
  targetControls: (t: TenantId) => ['tenant', seg(t), 'org', 'assign-targets', 'controls'] as const,
  periodSuggestion: (t: TenantId, frequency: string) =>
    ['tenant', seg(t), 'assessment', 'period-suggestion', frequency] as const,
}

export interface RoleAssignment {
  id: string
  scope: 'process' | 'control' | string
  target_id: string
  role_name: string
  user_id: string
  user_name: string | null
  created_at?: string
}

export interface RoleAssignmentPayload {
  scope: string
  target_id: string
  role_name: string
  user_id: string
  conflict_reason?: string | null
}

export interface TargetItem {
  id: string
  code: string
  name: string
}

export interface PeriodSuggestion {
  period_start: string
  period_end: string
  fiscal_year: number
  period_index: number
  fiscal_year_start_month: number
}

// ── 정책 ──
export function usePolicies() {
  const tenantId = useActiveTenantId()
  return useQuery({
    queryKey: orgExtraKeys.policies(tenantId),
    queryFn: async () => (await apiClient.get<ListResponse<TenantPolicy>>('/api/org/policies')).data,
    staleTime: 1000 * 30,
  })
}

export function useUpsertPolicy() {
  const qc = useQueryClient()
  const tenantId = useActiveTenantId()
  return useMutation({
    mutationFn: async (body: { policy_key: string; policy_value: string }) =>
      (await apiClient.put<TenantPolicy>('/api/org/policies', body)).data,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: orgExtraKeys.policies(tenantId) })
      qc.invalidateQueries({ queryKey: ['tenant', seg(tenantId), 'assessment', 'period-suggestion'] })
    },
  })
}

export function usePeriodSuggestion(frequency: string) {
  const tenantId = useActiveTenantId()
  return useQuery({
    queryKey: orgExtraKeys.periodSuggestion(tenantId, frequency),
    queryFn: async () =>
      (await apiClient.get<PeriodSuggestion>('/api/assessment/period-suggestion', { params: { frequency } })).data,
    staleTime: 1000 * 30,
  })
}

// ── 배정 ──
export function useAssignments() {
  const tenantId = useActiveTenantId()
  return useQuery({
    queryKey: orgExtraKeys.assignments(tenantId),
    queryFn: async () =>
      (await apiClient.get<ListResponse<RoleAssignment>>('/api/org/assignments', { params: { limit: 1000 } })).data,
    staleTime: 1000 * 30,
  })
}

export function useTargetProcesses() {
  const tenantId = useActiveTenantId()
  return useQuery({
    queryKey: orgExtraKeys.targetProcesses(tenantId),
    queryFn: async () =>
      (await apiClient.get<{ items: TargetItem[] }>('/api/rcm/processes', { params: { limit: 500 } })).data.items,
    staleTime: 1000 * 60,
  })
}

export function useTargetControls() {
  const tenantId = useActiveTenantId()
  return useQuery({
    queryKey: orgExtraKeys.targetControls(tenantId),
    queryFn: async () =>
      (await apiClient.get<{ items: TargetItem[] }>('/api/rcm/controls/search', { params: { limit: 1000 } })).data
        .items,
    staleTime: 1000 * 60,
  })
}

function useAssignmentInvalidation() {
  const qc = useQueryClient()
  const tenantId = useActiveTenantId()
  return () => {
    qc.invalidateQueries({ queryKey: orgExtraKeys.assignments(tenantId) })
    // 대시보드 조직별 집계·통제 역할 해석이 배정을 따른다
    qc.invalidateQueries({ queryKey: ['tenant', seg(tenantId), 'dashboard'] })
  }
}

export function useCreateAssignment() {
  const invalidate = useAssignmentInvalidation()
  return useMutation({
    mutationFn: async (body: RoleAssignmentPayload) =>
      (await apiClient.post<RoleAssignment>('/api/org/assignments', body)).data,
    onSuccess: invalidate,
  })
}

export function useDeleteAssignment() {
  const invalidate = useAssignmentInvalidation()
  return useMutation({
    mutationFn: async (id: string) => {
      await apiClient.delete(`/api/org/assignments/${id}`)
    },
    onSuccess: invalidate,
  })
}

export const errorDetail = (e: unknown, fallback: string): string => {
  const d = (e as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
  if (typeof d === 'string') return d
  if (Array.isArray(d)) return d.map((x) => (x as { msg?: string })?.msg ?? String(x)).join(', ')
  return fallback
}
