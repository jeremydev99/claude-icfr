import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import apiClient from '@/lib/axios'
import { useActiveTenantId } from '@/features/auth/store'
import type { Board } from './linkBoard.pure'

const key = (tid: string | null) => ['control-links', tid]

export function useBoard() {
  const tid = useActiveTenantId()
  return useQuery({ queryKey: key(tid), queryFn: async () => (await apiClient.get<Board>('/api/control-links/board')).data })
}

/** 보드 쓰기 — 끝나면 보드와 커버리지를 다시 읽는다 */
function useBoardWrite<TBody, TOut>(fn: (b: TBody) => Promise<TOut>) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: fn,
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['control-links'] })
      void qc.invalidateQueries({ queryKey: ['scoping'] })
    },
  })
}

export const useAutoMatch = () => useBoardWrite(async () => (await apiClient.post<{ added: number }>('/api/control-links/auto')).data)
export const useAddLink = () => useBoardWrite(async (b: { control_id: string; account_key: string }) =>
  (await apiClient.post('/api/control-links/links', b)).data)
export const useRemoveLink = () => useBoardWrite(async (id: string) =>
  (await apiClient.delete<{ result: string }>(`/api/control-links/links/${id}`)).data)
export const useSubmitLinks = () => useBoardWrite(async (note: string) =>
  (await apiClient.post<{ proposal_id: string }>('/api/control-links/submit', { note: note || null })).data)

export const errDetail = (e: unknown, f: string) =>
  (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? f
