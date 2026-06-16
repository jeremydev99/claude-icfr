import apiClient from '@/lib/axios'
import type {
  TestRun,
  TestRunCreatePayload,
  TestRunListResponse,
  TestRunSearchParams,
  TestStatusHistory,
  TestStep,
  TestStepCreatePayload,
  TestStepUpdatePayload,
  TestRunUpdatePayload,
  TransitionRequest,
} from '../types'

export async function fetchTestRuns(params: TestRunSearchParams): Promise<TestRunListResponse> {
  const cleanParams: Record<string, unknown> = {}
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== '') {
      cleanParams[key] = value
    }
  }
  const res = await apiClient.get<TestRunListResponse>('/api/test/runs', { params: cleanParams })
  return res.data
}

export async function createTestRun(payload: TestRunCreatePayload): Promise<TestRun> {
  const res = await apiClient.post<TestRun>('/api/test/runs', payload)
  return res.data
}

export async function fetchTestRunDetail(id: string): Promise<TestRun> {
  const res = await apiClient.get<TestRun>(`/api/test/runs/${id}`)
  return res.data
}

export async function fetchTestRunHistory(id: string): Promise<{ items: TestStatusHistory[] }> {
  const res = await apiClient.get<{ items: TestStatusHistory[] }>(`/api/test/runs/${id}/history`)
  return res.data
}

export async function transitionTestRun({ id, payload }: { id: string; payload: TransitionRequest }): Promise<void> {
  await apiClient.post(`/api/test/runs/${id}/transition`, payload)
}

export async function updateTestRun({ id, payload }: { id: string; payload: TestRunUpdatePayload }): Promise<TestRun> {
  const res = await apiClient.patch<TestRun>(`/api/test/runs/${id}`, payload)
  return res.data
}

export async function fetchTestSteps(runId: string): Promise<{ items: TestStep[] }> {
  const res = await apiClient.get<{ items: TestStep[] }>('/api/test/steps', { params: { run_id: runId } })
  return res.data
}

export async function createTestStep(payload: TestStepCreatePayload): Promise<TestStep> {
  const res = await apiClient.post<TestStep>('/api/test/steps', payload)
  return res.data
}

export async function updateTestStep({ id, payload }: { id: string; payload: TestStepUpdatePayload }): Promise<TestStep> {
  const res = await apiClient.patch<TestStep>(`/api/test/steps/${id}`, payload)
  return res.data
}

export async function deleteTestStep(id: string): Promise<void> {
  await apiClient.delete(`/api/test/steps/${id}`)
}
