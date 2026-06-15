import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { fetchTestRuns, createTestRun } from './testRunsApi'
import type { TestRunSearchParams } from '../types'

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
