import { MutationCache, QueryClient } from '@tanstack/react-query'

export const queryClient: QueryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: 1, staleTime: 1000 * 60 * 5 },
  },
  // 결재·상신·반려 등 무엇이든 저장이 끝나면 상단 알림 배지·결재 진입로를 바로 다시 센다(13.9-114).
  // 결재 화면마다 무효화를 따로 달면 한 곳을 빠뜨리기 쉬워 한 곳에 둔다.
  mutationCache: new MutationCache({
    onSettled: () => { void queryClient.invalidateQueries({ queryKey: ['governance-inbox'] }) },
  }),
})
