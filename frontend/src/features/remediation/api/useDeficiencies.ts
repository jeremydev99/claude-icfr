import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  fetchDeficiencies,
  createDeficiency,
  updateDeficiency,
  deleteDeficiency,
} from './deficiencyApi'
import type { DeficiencyCreatePayload, DeficiencyUpdatePayload } from '../types'
import { queryKeys } from '@/lib/queryKeys'
import { useActiveTenantId } from '@/features/auth/store'

export function useDeficiencies(params: { skip?: number; limit?: number } = {}) {
  const tenantId = useActiveTenantId()
  return useQuery({
    queryKey: queryKeys.remediation.deficiencies(tenantId, params),
    queryFn: () => fetchDeficiencies(params),
    placeholderData: (prev) => prev,
    staleTime: 1000 * 30,
  })
}

export function useCreateDeficiency() {
  const queryClient = useQueryClient()
  const tenantId = useActiveTenantId()
  return useMutation({
    mutationFn: (payload: DeficiencyCreatePayload) => createDeficiency(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.remediation.deficienciesAll(tenantId) })
    },
  })
}

export function useUpdateDeficiency() {
  const queryClient = useQueryClient()
  const tenantId = useActiveTenantId()
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: DeficiencyUpdatePayload }) =>
      updateDeficiency({ id, payload }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.remediation.deficienciesAll(tenantId) })
    },
  })
}

export function useDeleteDeficiency() {
  const queryClient = useQueryClient()
  const tenantId = useActiveTenantId()
  return useMutation({
    mutationFn: (id: string) => deleteDeficiency(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.remediation.deficienciesAll(tenantId) })
    },
  })
}
