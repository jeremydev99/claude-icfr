import { useQuery } from '@tanstack/react-query'
import { fetchUsers, fetchUserDetail } from './usersApi'

export function useUsers(params: { skip?: number; limit?: number } = {}) {
  return useQuery({
    queryKey: ['users', params],
    queryFn: () => fetchUsers(params),
    staleTime: 1000 * 60 * 5,
  })
}

export function useUserDetail(id: string | null) {
  return useQuery({
    queryKey: ['users', id],
    queryFn: () => fetchUserDetail(id!),
    enabled: !!id,
    staleTime: 1000 * 60 * 5,
  })
}
