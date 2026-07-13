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

export function usePlans(params: { skip?: number; limit?: number } = {}) {
  return useQuery({
    queryKey: queryKeys.remediation.plans(params),
    queryFn: () => fetchPlans(params),
    placeholderData: (prev) => prev,
    staleTime: 1000 * 30,
  })
}

export function useCreatePlan() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: RemediationPlanCreatePayload) => createPlan(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.remediation.plansAll() })
    },
  })
}

export function usePlanDetail(id: string | null) {
  return useQuery({
    queryKey: queryKeys.remediation.planDetail(id),
    queryFn: () => fetchPlanDetail(id!),
    enabled: !!id,
  })
}

export function useUpdatePlan() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: RemediationPlanUpdatePayload }) =>
      updatePlan({ id, payload }),
    onSuccess: (_data, { id }) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.remediation.planDetail(id) })
      queryClient.invalidateQueries({ queryKey: queryKeys.remediation.plansAll() })
    },
  })
}

export function useDeletePlan() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => deletePlan(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.remediation.plansAll() })
    },
  })
}

export function useTransitionPlan() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: RemediationTransitionRequest }) =>
      transitionPlan({ id, payload }),
    onSuccess: (_data, { id }) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.remediation.planDetail(id) })
      queryClient.invalidateQueries({ queryKey: queryKeys.remediation.planHistory(id) })
      queryClient.invalidateQueries({ queryKey: queryKeys.remediation.plansAll() })
    },
  })
}

export function usePlanHistory(id: string | null) {
  return useQuery({
    queryKey: queryKeys.remediation.planHistory(id),
    queryFn: () => fetchPlanHistory(id!),
    enabled: !!id,
  })
}
