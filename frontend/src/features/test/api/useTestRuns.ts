import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { fetchTestRuns, createTestRun, fetchTestRunDetail, fetchTestRunHistory, transitionTestRun } from './testRunsApi'
import type { TestRunSearchParams, TransitionRequest } from '../types'

export function useTestRuns(params: TestRunSearchParams) {
  return useQuery({
    queryKey: ['testRuns', params],
    queryFn: () => fetchTestRuns(params),
    placeholderData: (prev) => prev,
    staleTime: 1000 * 30,
  })
}

export function useCreateTestRun() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: createTestRun,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['testRuns'] })
    },
  })
}

export function useTestRunDetail(id: string | null) {
  return useQuery({
    queryKey: ['testRunDetail', id],
    queryFn: () => fetchTestRunDetail(id!),
    enabled: !!id,
  })
}

export function useTestRunHistory(id: string | null) {
  return useQuery({
    queryKey: ['testRunHistory', id],
    queryFn: () => fetchTestRunHistory(id!),
    enabled: !!id,
  })
}

export function useTransitionTestRun() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: TransitionRequest }) =>
      transitionTestRun({ id, payload }),
    onSuccess: (_data, { id }) => {
      queryClient.invalidateQueries({ queryKey: ['testRunDetail', id] })
      queryClient.invalidateQueries({ queryKey: ['testRunHistory', id] })
      queryClient.invalidateQueries({ queryKey: ['testRuns'] })
    },
  })
}
