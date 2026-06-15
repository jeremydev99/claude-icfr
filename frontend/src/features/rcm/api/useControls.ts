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

export function useControls(params: ControlSearchParams) {
  return useQuery<ControlListResponse>({
    queryKey: ['controls', params],
    queryFn: () => fetchControls(params),
    placeholderData: (previous) => previous,
    staleTime: 1000 * 30,
  })
}

export function useCreateControl() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: createControl,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['controls'] })
    },
  })
}

export function useUpdateControl() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: ControlUpdatePayload }) =>
      updateControlById(id, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['controls'] })
    },
  })
}

export function useDeleteControl() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: deleteControl,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['controls'] })
    },
  })
}
