import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  fetchControls,
  createControl,
  updateControlById,
  deleteControl,
} from './controlsApi'
import type {
  ControlSearchParams,
  ControlListResponse,
  ControlUpdatePayload,
} from '../types'
import { queryKeys } from '@/lib/queryKeys'
import { useActiveTenantId } from '@/features/auth/store'

export function useControls(params: ControlSearchParams) {
  const tenantId = useActiveTenantId()
  return useQuery<ControlListResponse>({
    queryKey: queryKeys.rcm.controls(tenantId, params),
    queryFn: () => fetchControls(params),
    placeholderData: (previous) => previous,
    staleTime: 1000 * 30,
  })
}

export function useCreateControl() {
  const queryClient = useQueryClient()
  const tenantId = useActiveTenantId()
  return useMutation({
    mutationFn: createControl,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.rcm.controlsAll(tenantId) })
    },
  })
}

export function useUpdateControl() {
  const queryClient = useQueryClient()
  const tenantId = useActiveTenantId()
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: ControlUpdatePayload }) =>
      updateControlById(id, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.rcm.controlsAll(tenantId) })
    },
  })
}

export function useDeleteControl() {
  const queryClient = useQueryClient()
  const tenantId = useActiveTenantId()
  return useMutation({
    mutationFn: deleteControl,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.rcm.controlsAll(tenantId) })
    },
  })
}
