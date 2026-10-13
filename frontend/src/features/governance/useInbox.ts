import { useQuery } from '@tanstack/react-query'
import apiClient from '@/lib/axios'
import { useActiveTenantId } from '@/features/auth/store'
import type { InboxItem } from './types'

/**
 * 내가 지금 처리할 결재·할 일 — 대시보드 "내 결재 대기"와 상단 알림 배지가 같은 목록을 쓴다.
 * 다른 사람이 결재를 올리면 화면을 새로고침하지 않아도 1분 안에 배지에 나타난다.
 */
export function useInbox() {
  const tenantId = useActiveTenantId()
  return useQuery({
    queryKey: ['governance-inbox', tenantId],
    queryFn: async () => (await apiClient.get<InboxItem[]>('/api/governance/inbox')).data,
    staleTime: 30_000,
    refetchInterval: 60_000,
    refetchOnWindowFocus: true,
  })
}
