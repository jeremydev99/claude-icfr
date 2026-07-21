import apiClient from '@/lib/axios'
import type { RawcCreatePayload, RawcUpdatePayload } from '../types'
import type { ControlRiskAssessmentDto, RawcListResponseDto } from './dto'

export async function fetchRawcByControl(
  controlId: string,
  fiscalYear?: number,
): Promise<RawcListResponseDto> {
  const params: Record<string, unknown> = {}
  if (fiscalYear !== undefined) params.fiscal_year = fiscalYear
  const res = await apiClient.get<RawcListResponseDto>(
    `/api/test/rawc/by-control/${controlId}`,
    { params },
  )
  return res.data
}

export async function createRawc(payload: RawcCreatePayload): Promise<ControlRiskAssessmentDto> {
  const res = await apiClient.post<ControlRiskAssessmentDto>('/api/test/rawc', payload)
  return res.data
}

export async function updateRawc(
  id: string,
  payload: RawcUpdatePayload,
): Promise<ControlRiskAssessmentDto> {
  const res = await apiClient.patch<ControlRiskAssessmentDto>(`/api/test/rawc/${id}`, payload)
  return res.data
}
