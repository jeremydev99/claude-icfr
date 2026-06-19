import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { fetchRawcByControl, createRawc, updateRawc } from './rawcApi'
import type { RawcCreatePayload, RawcUpdatePayload } from '../types'

export function useRawcByControl(controlId: string | null, fiscalYear: number) {
  return useQuery({
    queryKey: ['rawc', controlId, fiscalYear],
    queryFn: () => fetchRawcByControl(controlId!, fiscalYear),
    enabled: !!controlId,
    staleTime: 1000 * 30,
  })
}

export function useCreateRawc() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: RawcCreatePayload) => createRawc(payload),
    onSuccess: (_data, payload) => {
      queryClient.invalidateQueries({ queryKey: ['rawc', payload.control_id, payload.fiscal_year] })
    },
  })
}

export function useUpdateRawc() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: RawcUpdatePayload; controlId: string; fiscalYear: number }) =>
      updateRawc(id, payload),
    onSuccess: (_data, { controlId, fiscalYear }) => {
      queryClient.invalidateQueries({ queryKey: ['rawc', controlId, fiscalYear] })
    },
  })
}
