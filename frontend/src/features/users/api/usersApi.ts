import apiClient from '@/lib/axios'
import type { User, UserListResponse } from '../types'

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
