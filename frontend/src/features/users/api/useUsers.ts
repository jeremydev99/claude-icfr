import { useQuery } from '@tanstack/react-query'
import { fetchUsers } from './usersApi'

export function useUsers(params: { skip?: number; limit?: number } = {}) {
  return useQuery({
    queryKey: ['users', params],
    queryFn: () => fetchUsers(params),
    staleTime: 1000 * 60 * 5,
  })
}
