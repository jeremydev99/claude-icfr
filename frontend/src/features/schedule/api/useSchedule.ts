import { useQueries, useQuery } from '@tanstack/react-query'
import apiClient from '@/lib/axios'
import { useActiveTenantId } from '@/features/auth/store'
import { startMonthFromPolicies } from '../schedule.pure'

export interface CycleItem {
  id: string
  kind: string
  frequency: string
  name: string
  period_start: string
  period_end: string
  due_date: string | null
  status: string
  target_count: number | null
}

interface ListResp<T> {
  items: T[]
  total: number
}

const key = (tenantId: string | null, ...rest: unknown[]) => ['tenant', tenantId ?? 'no-tenant', 'schedule', ...rest]

export function useFiscalStartMonth() {
  const tenantId = useActiveTenantId()
  return useQuery({
    queryKey: key(tenantId, 'policies'),
    queryFn: async () => {
      const res = await apiClient.get<ListResp<{ policy_key: string; policy_value: string }>>('/api/org/policies')
      return startMonthFromPolicies(res.data.items)
    },
    staleTime: 5 * 60_000,
  })
}

export function useCycles() {
  const tenantId = useActiveTenantId()
  return useQuery({
    queryKey: key(tenantId, 'cycles'),
    queryFn: async () => (await apiClient.get<ListResp<CycleItem>>('/api/assessment/cycles', { params: { limit: 100 } })).data.items,
  })
}

/** 진행 중 회차만 미완 건수를 조회한다(최대 10개) — 마감·승인 회차는 조회하지 않는다. */
export function useIncompleteCounts(cycles: CycleItem[]) {
  const tenantId = useActiveTenantId()
  const targets = cycles.filter((c) => c.status === 'open').slice(0, 10)
  const results = useQueries({
    queries: targets.map((c) => ({
      queryKey: key(tenantId, 'incomplete', c.id),
      queryFn: async () => (await apiClient.get<ListResp<unknown>>(`/api/assessment/cycles/${c.id}/incomplete`)).data.total,
    })),
  })
  const map: Record<string, number | undefined> = {}
  targets.forEach((c, i) => {
    map[c.id] = results[i]?.data
  })
  return map
}
