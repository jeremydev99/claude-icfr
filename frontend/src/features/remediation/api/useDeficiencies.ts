import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  fetchDeficiencies,
  createDeficiency,
  updateDeficiency,
  deleteDeficiency,
} from './deficiencyApi'
import type { DeficiencyCreatePayload, DeficiencyUpdatePayload } from '../types'

export function useDeficiencies(params: { skip?: number; limit?: number } = {}) {
  return useQuery({
    queryKey: ['deficiencies', params],
    queryFn: () => fetchDeficiencies(params),
    placeholderData: (prev) => prev,
    staleTime: 1000 * 30,
  })
}

export function useCreateDeficiency() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: DeficiencyCreatePayload) => createDeficiency(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['deficiencies'] })
    },
  })
}

export function useUpdateDeficiency() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: DeficiencyUpdatePayload }) =>
      updateDeficiency({ id, payload }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['deficiencies'] })
    },
  })
}

export function useDeleteDeficiency() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => deleteDeficiency(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['deficiencies'] })
    },
  })
}
