import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import apiClient from '@/lib/axios'
import { useActiveTenantId } from '@/features/auth/store'
import type { CycleItem } from '@/features/schedule/api/useSchedule'

export interface CycleCreatePayload {
  kind: string
  frequency: string
  name: string
  fiscal_year: number
  period_index: number
  period_start: string
  period_end: string
  due_date?: string | null
}

export interface PeriodSuggestion {
  period_start: string
  period_end: string
  fiscal_year: number
  period_index: number
  fiscal_year_start_month: number
}

const seg = (t: string | null) => t ?? 'no-tenant'

/** 기간 제안 — 주기·회계연도·차수가 바뀔 때마다 다시 받는다. 강제가 아닌 제안값(ADR-0032 §2.2). */
export function useCyclePeriodSuggestion(frequency: string, fiscalYear: number, periodIndex: number) {
  const tenantId = useActiveTenantId()
  return useQuery({
    queryKey: ['tenant', seg(tenantId), 'assessment', 'period-suggestion', frequency, fiscalYear, periodIndex],
    queryFn: async () =>
      (
        await apiClient.get<PeriodSuggestion>('/api/assessment/period-suggestion', {
          params: { frequency, fiscal_year: fiscalYear, period_index: periodIndex },
        })
      ).data,
    staleTime: 5 * 60_000,
  })
}

export function useCreateCycle() {
  const qc = useQueryClient()
  const tenantId = useActiveTenantId()
  return useMutation({
    mutationFn: async (payload: CycleCreatePayload) =>
      (await apiClient.post<CycleItem>('/api/assessment/cycles', payload)).data,
    onSuccess: () => {
      // 회차 목록은 일정관리 키(['tenant', t, 'schedule', 'cycles'])를 일정관리·증빙 업로드가 함께 쓴다
      qc.invalidateQueries({ queryKey: ['tenant', seg(tenantId), 'schedule'] })
    },
  })
}
