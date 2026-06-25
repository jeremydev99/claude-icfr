import apiClient from '@/lib/axios'
import type {
  UserRole,
  UserRoleListResponse,
  UserRoleCreatePayload,
  UserRoleUpdatePayload,
} from '../types'

export async function fetchUserRoles(
  params: { skip?: number; limit?: number } = {}
): Promise<UserRoleListResponse> {
  const res = await apiClient.get<UserRoleListResponse>('/api/users/roles/list', { params })
  return res.data
}

export async function createUserRole(payload: UserRoleCreatePayload): Promise<UserRole> {
  const res = await apiClient.post<UserRole>('/api/users/roles', payload)
  return res.data
}

export async function fetchUserRoleDetail(id: string): Promise<UserRole> {
  const res = await apiClient.get<UserRole>(`/api/users/roles/${id}`)
  return res.data
}

export async function updateUserRole(
  id: string,
  payload: UserRoleUpdatePayload
): Promise<UserRole> {
  const res = await apiClient.patch<UserRole>(`/api/users/roles/${id}`, payload)
  return res.data
}

export async function deleteUserRole(id: string): Promise<void> {
  await apiClient.delete(`/api/users/roles/${id}`)
}
