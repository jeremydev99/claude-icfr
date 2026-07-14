import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { fetchRawcByControl, createRawc, updateRawc } from './rawcApi'
import type { RawcCreatePayload, RawcUpdatePayload } from '../types'
import { queryKeys } from '@/lib/queryKeys'
import { useActiveTenantId } from '@/features/auth/store'

export function useRawcByControl(controlId: string | null, fiscalYear: number) {
  const tenantId = useActiveTenantId()
  return useQuery({
    queryKey: queryKeys.rcm.rawc(tenantId, controlId, fiscalYear),
    queryFn: () => fetchRawcByControl(controlId!, fiscalYear),
    enabled: !!controlId,
    staleTime: 1000 * 30,
  })
}

export function useCreateRawc() {
  const queryClient = useQueryClient()
  const tenantId = useActiveTenantId()
  return useMutation({
    mutationFn: (payload: RawcCreatePayload) => createRawc(payload),
    onSuccess: (_data, payload) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.rcm.rawc(tenantId, payload.control_id, payload.fiscal_year) })
    },
  })
}

export function useUpdateRawc() {
  const queryClient = useQueryClient()
  const tenantId = useActiveTenantId()
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: RawcUpdatePayload; controlId: string; fiscalYear: number }) =>
      updateRawc(id, payload),
    onSuccess: (_data, { controlId, fiscalYear }) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.rcm.rawc(tenantId, controlId, fiscalYear) })
    },
  })
}
