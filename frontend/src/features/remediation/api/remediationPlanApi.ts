import apiClient from '@/lib/axios'
import type {
  RemediationPlan,
  RemediationPlanCreatePayload,
  RemediationPlanListResponse,
  RemediationPlanUpdatePayload,
  RemediationStatusHistory,
  RemediationTransitionRequest,
} from '../types'

export async function fetchPlans(params: { skip?: number; limit?: number }): Promise<RemediationPlanListResponse> {
  const res = await apiClient.get<RemediationPlanListResponse>('/api/remediation/plans', { params })
  return res.data
}

export async function createPlan(payload: RemediationPlanCreatePayload): Promise<RemediationPlan> {
  const res = await apiClient.post<RemediationPlan>('/api/remediation/plans', payload)
  return res.data
}

export async function fetchPlanDetail(id: string): Promise<RemediationPlan> {
  const res = await apiClient.get<RemediationPlan>(`/api/remediation/plans/${id}`)
  return res.data
}

export async function updatePlan({ id, payload }: { id: string; payload: RemediationPlanUpdatePayload }): Promise<RemediationPlan> {
  const res = await apiClient.patch<RemediationPlan>(`/api/remediation/plans/${id}`, payload)
  return res.data
}

export async function deletePlan(id: string): Promise<void> {
  await apiClient.delete(`/api/remediation/plans/${id}`)
}

export async function transitionPlan({ id, payload }: { id: string; payload: RemediationTransitionRequest }): Promise<RemediationPlan> {
  const res = await apiClient.post<RemediationPlan>(`/api/remediation/plans/${id}/transition`, payload)
  return res.data
}

export async function fetchPlanHistory(id: string): Promise<{ items: RemediationStatusHistory[]; total: number }> {
  const res = await apiClient.get<{ items: RemediationStatusHistory[]; total: number }>(`/api/remediation/plans/${id}/history`)
  return res.data
}
