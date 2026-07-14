import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  fetchPlans,
  createPlan,
  fetchPlanDetail,
  updatePlan,
  deletePlan,
  transitionPlan,
  fetchPlanHistory,
} from './remediationPlanApi'
import type { RemediationPlanCreatePayload, RemediationPlanUpdatePayload, RemediationTransitionRequest } from '../types'
import { queryKeys } from '@/lib/queryKeys'
import { useActiveTenantId } from '@/features/auth/store'

export function usePlans(params: { skip?: number; limit?: number } = {}) {
  const tenantId = useActiveTenantId()
  return useQuery({
    queryKey: queryKeys.remediation.plans(tenantId, params),
    queryFn: () => fetchPlans(params),
    placeholderData: (prev) => prev,
    staleTime: 1000 * 30,
  })
}

export function useCreatePlan() {
  const queryClient = useQueryClient()
  const tenantId = useActiveTenantId()
  return useMutation({
    mutationFn: (payload: RemediationPlanCreatePayload) => createPlan(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.remediation.plansAll(tenantId) })
    },
  })
}

export function usePlanDetail(id: string | null) {
  const tenantId = useActiveTenantId()
  return useQuery({
    queryKey: queryKeys.remediation.planDetail(tenantId, id),
    queryFn: () => fetchPlanDetail(id!),
    enabled: !!id,
  })
}

export function useUpdatePlan() {
  const queryClient = useQueryClient()
  const tenantId = useActiveTenantId()
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: RemediationPlanUpdatePayload }) =>
      updatePlan({ id, payload }),
    onSuccess: (_data, { id }) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.remediation.planDetail(tenantId, id) })
      queryClient.invalidateQueries({ queryKey: queryKeys.remediation.plansAll(tenantId) })
    },
  })
}

export function useDeletePlan() {
  const queryClient = useQueryClient()
  const tenantId = useActiveTenantId()
  return useMutation({
    mutationFn: (id: string) => deletePlan(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.remediation.plansAll(tenantId) })
    },
  })
}

export function useTransitionPlan() {
  const queryClient = useQueryClient()
  const tenantId = useActiveTenantId()
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: RemediationTransitionRequest }) =>
      transitionPlan({ id, payload }),
    onSuccess: (_data, { id }) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.remediation.planDetail(tenantId, id) })
      queryClient.invalidateQueries({ queryKey: queryKeys.remediation.planHistory(tenantId, id) })
      queryClient.invalidateQueries({ queryKey: queryKeys.remediation.plansAll(tenantId) })
    },
  })
}

export function usePlanHistory(id: string | null) {
  const tenantId = useActiveTenantId()
  return useQuery({
    queryKey: queryKeys.remediation.planHistory(tenantId, id),
    queryFn: () => fetchPlanHistory(id!),
    enabled: !!id,
  })
}
