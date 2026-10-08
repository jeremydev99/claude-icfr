import apiClient from '@/lib/axios'
import type { LoginEvent, User, UserListResponse, UserCreatePayload, UserUpdatePayload, ResetPasswordPayload, SetupLink, UserCreated } from '../types'

export async function fetchUsers(
  params: { skip?: number; limit?: number } = {}
): Promise<UserListResponse> {
  const res = await apiClient.get<UserListResponse>('/api/users/', { params })
  return res.data
}

export async function fetchUserDetail(id: string): Promise<User> {
  const res = await apiClient.get<User>(`/api/users/${id}`)
  return res.data
}

export async function createUser(body: UserCreatePayload): Promise<UserCreated> {
  const res = await apiClient.post<UserCreated>('/api/users/', body)
  return res.data
}

/** 설정 링크 (재)발급 — 초대 대기면 초대, 아니면 재설정. 이전 링크는 취소된다(ADR-0041) */
export async function issueSetupLink(id: string): Promise<SetupLink> {
  return (await apiClient.post<SetupLink>(`/api/users/${id}/setup-link`)).data
}

export async function updateUser(id: string, body: UserUpdatePayload): Promise<User> {
  const res = await apiClient.patch<User>(`/api/users/${id}`, body)
  return res.data
}

export async function deleteUser(id: string): Promise<void> {
  await apiClient.delete(`/api/users/${id}`)
}

export async function unlockUser(id: string): Promise<void> {
  await apiClient.post(`/api/users/${id}/unlock`)
}

export async function fetchLoginEvents(
  params: { user_id?: string; failed_only?: boolean; limit?: number } = {}
): Promise<LoginEvent[]> {
  const res = await apiClient.get<LoginEvent[]>('/api/users/login-events', { params })
  return res.data
}

export async function resetUserPassword(id: string, body: ResetPasswordPayload): Promise<void> {
  await apiClient.post(`/api/users/${id}/reset-password`, body)
}

/** 시험 메일 — 요청한 시스템관리자 본인 주소로 보낸다(2026-10-08). sent=null 이면 서버에 메일 설정이 없다. */
export async function sendTestMail(): Promise<{ to: string; sent: boolean | null; error: string | null }> {
  return (await apiClient.post('/api/notification/mail/test')).data
}
