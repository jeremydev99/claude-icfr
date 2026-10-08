import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import apiClient from '@/lib/axios'
import { useActiveTenantId } from '@/features/auth/store'

export type ExternalType = 'advisor' | 'auditor' | 'committee' | 'specialist'

export interface Invitation {
  id: string
  email: string
  display_name: string
  user_type: ExternalType
  type_label: string
  organization: string
  modules: string[] | null
  valid_from: string
  valid_until: string
  note: string | null
  status: 'pending_approval' | 'approved' | 'accepted' | 'revoked' | 'expired'
  status_label: string
  requested_by: string | null
  approved_by: string | null
  token_expires_at: string | null
  accepted_at: string | null
  created_at: string
  invite_url: string | null
  mail_sent?: boolean | null
  mail_error?: string | null
}

export interface ExternalUser {
  id: string
  user_id: string
  email: string
  display_name: string
  user_type: ExternalType
  type_label: string
  organization: string
  modules: string[] | null
  valid_from: string
  valid_until: string
  status: 'active' | 'revoked'
  mfa_enabled: boolean
  last_login_at: string | null
  last_reviewed_at: string | null
  last_reviewed_by: string | null
}

export interface AccessReview {
  id: string
  reviewed_by: string | null
  note: string | null
  count: number
  created_at: string
}

export interface InviteCreate {
  email: string
  display_name: string
  user_type: ExternalType
  organization: string
  modules?: string[] | null
  valid_until: string
  note?: string | null
}

const key = (tid: string | null, k: string) => ['external', tid, k]

export function useInvitations() {
  const tid = useActiveTenantId()
  return useQuery({ queryKey: key(tid, 'inv'), queryFn: async () => (await apiClient.get<Invitation[]>('/api/external/invitations')).data })
}
export function useExternalUsers() {
  const tid = useActiveTenantId()
  return useQuery({ queryKey: key(tid, 'users'), queryFn: async () => (await apiClient.get<ExternalUser[]>('/api/external/users')).data })
}
export function useAccessReviews() {
  const tid = useActiveTenantId()
  return useQuery({ queryKey: key(tid, 'reviews'), queryFn: async () => (await apiClient.get<AccessReview[]>('/api/external/reviews')).data })
}

/** 외부 사용자 관련 쓰기 — 끝나면 이 탭의 목록을 전부 다시 읽는다 */
export function useExternalAction<TBody, TOut>(fn: (b: TBody) => Promise<TOut>) {
  const qc = useQueryClient()
  return useMutation({ mutationFn: fn, onSuccess: () => qc.invalidateQueries({ queryKey: ['external'] }) })
}

export const api = {
  invite: async (b: InviteCreate) => (await apiClient.post<Invitation>('/api/external/invitations', b)).data,
  approve: async (id: string) => (await apiClient.post<Invitation>(`/api/external/invitations/${id}/approve`)).data,
  revokeInvite: async (b: { id: string; reason?: string }) =>
    (await apiClient.post<Invitation>(`/api/external/invitations/${b.id}/revoke`, { reason: b.reason ?? null })).data,
  update: async (b: { id: string; valid_until?: string; modules?: string[] }) =>
    (await apiClient.patch<ExternalUser>(`/api/external/users/${b.id}`, { valid_until: b.valid_until ?? null, modules: b.modules ?? null })).data,
  revokeUser: async (b: { id: string; reason?: string }) =>
    (await apiClient.post<ExternalUser>(`/api/external/users/${b.id}/revoke`, { reason: b.reason ?? null })).data,
  review: async (note: string) => (await apiClient.post<AccessReview>('/api/external/reviews', { reason: note || null })).data,
  mfaReset: async (userId: string) => (await apiClient.post<{ detail: string }>(`/api/users/${userId}/mfa-reset`)).data,
}

export const TYPE_OPTIONS: { value: ExternalType; label: string; hint: string }[] = [
  { value: 'advisor', label: 'PA회계법인(ICFR 자문)', hint: '작성·검토 요청까지(일반관리자처럼). 승인은 못 합니다' },
  { value: 'auditor', label: '외부감사인', hint: '전 모듈 조회 전용' },
  { value: 'committee', label: '감사위원회·사외이사', hint: '보고서·현황판·미비점 조회 전용' },
  { value: 'specialist', label: '세무·기장대리인', hint: '고른 모듈만 작성(재무제표). 확정은 내부회계관리자' },
]
