import apiClient from '@/lib/axios'

export interface UserRead {
  id: string
  email: string
  display_name: string
  role: string
  is_active: boolean
  created_at: string
}

export interface UserListResponse {
  items: UserRead[]
  total: number
  skip: number
  limit: number
}

export async function fetchUsers(
  params: { skip?: number; limit?: number } = {}
): Promise<UserListResponse> {
  const res = await apiClient.get<UserListResponse>('/api/users/', { params })
  return res.data
}
