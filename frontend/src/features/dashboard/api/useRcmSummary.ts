import { useQuery } from '@tanstack/react-query'
import { fetchRcmSummary } from './summaryApi'
import { queryKeys } from '@/lib/queryKeys'
import { useActiveTenantId } from '@/features/auth/store'

export function useRcmSummary() {
  const tenantId = useActiveTenantId()
  return useQuery({
    queryKey: queryKeys.dashboard.rcmSummary(tenantId),
    queryFn: fetchRcmSummary,
    staleTime: 1000 * 60,
  })
}
