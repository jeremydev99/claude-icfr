import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  fetchUserRoles,
  createUserRole,
  updateUserRole,
  deleteUserRole,
} from './userRolesApi'
import type { UserRoleCreatePayload, UserRoleUpdatePayload } from '../types'
import { queryKeys } from '@/lib/queryKeys'

export function useUserRoles(params: { skip?: number; limit?: number } = {}) {
  return useQuery({
    queryKey: queryKeys.users.roles(params),
    queryFn: () => fetchUserRoles(params),
    staleTime: 1000 * 60 * 5,
  })
}

export function useCreateUserRole() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (payload: UserRoleCreatePayload) => createUserRole(payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.users.rolesAll() }),
  })
}

export function useUpdateUserRole() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: UserRoleUpdatePayload }) =>
      updateUserRole(id, payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.users.rolesAll() }),
  })
}

export function useDeleteUserRole() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => deleteUserRole(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.users.rolesAll() }),
  })
}
