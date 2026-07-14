import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  fetchTestRuns, createTestRun, fetchTestRunDetail, fetchTestRunHistory, transitionTestRun,
  updateTestRun, fetchTestSteps, createTestStep, updateTestStep, deleteTestStep,
} from './testRunsApi'
import type { TestRunSearchParams, TestRunUpdatePayload, TestStepCreatePayload, TestStepUpdatePayload, TransitionRequest } from '../types'
import { queryKeys } from '@/lib/queryKeys'
import { useActiveTenantId } from '@/features/auth/store'

export function useTestRuns(params: TestRunSearchParams) {
  const tenantId = useActiveTenantId()
  return useQuery({
    queryKey: queryKeys.test.testRuns(tenantId, params),
    queryFn: () => fetchTestRuns(params),
    placeholderData: (prev) => prev,
    staleTime: 1000 * 30,
  })
}

export function useCreateTestRun() {
  const queryClient = useQueryClient()
  const tenantId = useActiveTenantId()
  return useMutation({
    mutationFn: createTestRun,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.test.testRunsAll(tenantId) })
    },
  })
}

export function useTestRunDetail(id: string | null) {
  const tenantId = useActiveTenantId()
  return useQuery({
    queryKey: queryKeys.test.testRunDetail(tenantId, id),
    queryFn: () => fetchTestRunDetail(id!),
    enabled: !!id,
  })
}

export function useTestRunHistory(id: string | null) {
  const tenantId = useActiveTenantId()
  return useQuery({
    queryKey: queryKeys.test.testRunHistory(tenantId, id),
    queryFn: () => fetchTestRunHistory(id!),
    enabled: !!id,
  })
}

export function useTransitionTestRun() {
  const queryClient = useQueryClient()
  const tenantId = useActiveTenantId()
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: TransitionRequest }) =>
      transitionTestRun({ id, payload }),
    onSuccess: (_data, { id }) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.test.testRunDetail(tenantId, id) })
      queryClient.invalidateQueries({ queryKey: queryKeys.test.testRunHistory(tenantId, id) })
      queryClient.invalidateQueries({ queryKey: queryKeys.test.testRunsAll(tenantId) })
    },
  })
}

export function useUpdateTestRun() {
  const queryClient = useQueryClient()
  const tenantId = useActiveTenantId()
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: TestRunUpdatePayload }) =>
      updateTestRun({ id, payload }),
    onSuccess: (_data, { id }) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.test.testRunDetail(tenantId, id) })
      queryClient.invalidateQueries({ queryKey: queryKeys.test.testRunsAll(tenantId) })
    },
  })
}

export function useTestSteps(runId: string | null) {
  const tenantId = useActiveTenantId()
  return useQuery({
    queryKey: queryKeys.test.testSteps(tenantId, runId),
    queryFn: () => fetchTestSteps(runId!),
    enabled: !!runId,
  })
}

export function useCreateTestStep() {
  const queryClient = useQueryClient()
  const tenantId = useActiveTenantId()
  return useMutation({
    mutationFn: (payload: TestStepCreatePayload) => createTestStep(payload),
    onSuccess: (_data, payload) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.test.testSteps(tenantId, payload.test_run_id) })
    },
  })
}

export function useUpdateTestStep() {
  const queryClient = useQueryClient()
  const tenantId = useActiveTenantId()
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: TestStepUpdatePayload; runId: string }) =>
      updateTestStep({ id, payload }),
    onSuccess: (_data, { runId }) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.test.testSteps(tenantId, runId) })
    },
  })
}

export function useDeleteTestStep() {
  const queryClient = useQueryClient()
  const tenantId = useActiveTenantId()
  return useMutation({
    mutationFn: ({ id }: { id: string; runId: string }) => deleteTestStep(id),
    onSuccess: (_data, { runId }) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.test.testSteps(tenantId, runId) })
    },
  })
}
