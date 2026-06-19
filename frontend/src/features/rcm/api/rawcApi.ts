import apiClient from '@/lib/axios'
import type { ControlRiskAssessment, RawcCreatePayload, RawcUpdatePayload } from '../types'

export async function fetchRawcByControl(
  controlId: string,
  fiscalYear?: number,
): Promise<{ items: ControlRiskAssessment[]; total: number }> {
  const params: Record<string, unknown> = {}
  if (fiscalYear !== undefined) params.fiscal_year = fiscalYear
  const res = await apiClient.get<{ items: ControlRiskAssessment[]; total: number }>(
    `/api/test/rawc/by-control/${controlId}`,
    { params },
  )
  return res.data
}

export async function createRawc(payload: RawcCreatePayload): Promise<ControlRiskAssessment> {
  const res = await apiClient.post<ControlRiskAssessment>('/api/test/rawc', payload)
  return res.data
}

export async function updateRawc(
  id: string,
  payload: RawcUpdatePayload,
): Promise<ControlRiskAssessment> {
  const res = await apiClient.patch<ControlRiskAssessment>(`/api/test/rawc/${id}`, payload)
  return res.data
}
