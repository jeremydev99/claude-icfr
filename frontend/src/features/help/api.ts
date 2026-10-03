import { useQuery } from '@tanstack/react-query'
import apiClient from '@/lib/axios'
import type { HelpText } from './types'

/**
 * 도움말은 **tenant 비종속**(ADR-0035 §1 — 제품 문구이지 회사 데이터가 아니다)이라
 * queryKeys 의 tenant 프리픽스를 쓰지 않는다. 문구는 시드 재적재로만 바뀌므로 오래 캐시한다.
 */
const HELP_STALE_MS = 1000 * 60 * 30

export async function fetchHelpByPrefix(prefix: string): Promise<HelpText[]> {
  const res = await apiClient.get<HelpText[]>('/api/help', { params: { prefix } })
  return res.data
}

export async function fetchHelpByKey(key: string): Promise<HelpText | null> {
  try {
    const res = await apiClient.get<HelpText>(`/api/help/${encodeURIComponent(key)}`)
    return res.data
  } catch (err: unknown) {
    // 키가 없으면 404 — "아직 작성되지 않음"과 같은 상태로 보여준다(문구를 지어내지 않는다).
    if ((err as { response?: { status?: number } })?.response?.status === 404) return null
    throw err
  }
}

/** `prefix` 자신 또는 `prefix.` 로 시작하는 항목 전부. prefix 가 null 이면 부르지 않는다. */
export function useHelpByPrefix(prefix: string | null, enabled = true) {
  return useQuery({
    queryKey: ['help', 'prefix', prefix] as const,
    queryFn: () => fetchHelpByPrefix(prefix as string),
    enabled: enabled && prefix !== null,
    staleTime: HELP_STALE_MS,
  })
}

export function useHelpByKey(key: string | null, enabled = true) {
  return useQuery({
    queryKey: ['help', 'key', key] as const,
    queryFn: () => fetchHelpByKey(key as string),
    enabled: enabled && key !== null,
    staleTime: HELP_STALE_MS,
  })
}
