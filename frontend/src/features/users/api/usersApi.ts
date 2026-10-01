import apiClient from '@/lib/axios'
import type { LoginEvent, User, UserListResponse, UserCreatePayload, UserUpdatePayload, ResetPasswordPayload } from '../types'

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

export async function createUser(body: UserCreatePayload): Promise<User> {
  const res = await apiClient.post<User>('/api/users/', body)
  return res.data
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
