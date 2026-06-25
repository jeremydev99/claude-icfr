import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  fetchUserRoles,
  createUserRole,
  updateUserRole,
  deleteUserRole,
} from './userRolesApi'
import type { UserRoleCreatePayload, UserRoleUpdatePayload } from '../types'

const QUERY_KEY = 'userRoles'

export function useUserRoles(params: { skip?: number; limit?: number } = {}) {
  return useQuery({
    queryKey: [QUERY_KEY, params],
    queryFn: () => fetchUserRoles(params),
    staleTime: 1000 * 60 * 5,
  })
}

export function useCreateUserRole() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (payload: UserRoleCreatePayload) => createUserRole(payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: [QUERY_KEY] }),
  })
}

export function useUpdateUserRole() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: UserRoleUpdatePayload }) =>
      updateUserRole(id, payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: [QUERY_KEY] }),
  })
}

export function useDeleteUserRole() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => deleteUserRole(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: [QUERY_KEY] }),
  })
}
