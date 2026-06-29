import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { fetchUsers, fetchUserDetail, createUser, updateUser, deleteUser, resetUserPassword } from './usersApi'
import type { UserCreatePayload, UserUpdatePayload, ResetPasswordPayload } from '../types'

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

export function useCreateUser() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: UserCreatePayload) => createUser(body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['users'] }),
  })
}

export function useUpdateUser() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: UserUpdatePayload }) => updateUser(id, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['users'] }),
  })
}

export function useDeleteUser() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => deleteUser(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['users'] }),
  })
}

export function useResetPassword() {
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: ResetPasswordPayload }) =>
      resetUserPassword(id, body),
  })
}
