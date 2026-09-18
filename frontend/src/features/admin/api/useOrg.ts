import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  createDepartment,
  createMembership,
  deleteDepartment,
  deleteMembership,
  fetchDepartments,
  fetchMemberships,
  updateDepartment,
  updateMembership,
} from './orgApi'
import type { DepartmentPayload, MembershipPayload } from '../types'
import { queryKeys } from '@/lib/queryKeys'
import { useActiveTenantId } from '@/features/auth/store'

export function useDepartments() {
  const tenantId = useActiveTenantId()
  return useQuery({
    queryKey: queryKeys.org.departments(tenantId),
    queryFn: fetchDepartments,
    staleTime: 1000 * 60,
  })
}

export function useMemberships(departmentId?: string) {
  const tenantId = useActiveTenantId()
  const params = departmentId ? { department_id: departmentId } : {}
  return useQuery({
    queryKey: queryKeys.org.memberships(tenantId, params),
    queryFn: () => fetchMemberships(params),
    staleTime: 1000 * 30,
  })
}

/**
 * 부서·소속을 바꾸면 **대시보드 조직별 집계도 바뀐다**(통제책임자의 주 소속이 기준).
 * 소속만 무효화하면 대시보드가 옛 숫자를 들고 있으므로 함께 지운다.
 */
function useOrgInvalidation() {
  const queryClient = useQueryClient()
  const tenantId = useActiveTenantId()
  return () => {
    queryClient.invalidateQueries({ queryKey: queryKeys.org.departments(tenantId) })
    queryClient.invalidateQueries({ queryKey: queryKeys.org.membershipsAll(tenantId) })
    queryClient.invalidateQueries({ queryKey: queryKeys.dashboard.rcmSummary(tenantId) })
  }
}

export function useCreateDepartment() {
  const invalidate = useOrgInvalidation()
  return useMutation({ mutationFn: createDepartment, onSuccess: invalidate })
}

export function useUpdateDepartment() {
  const invalidate = useOrgInvalidation()
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: DepartmentPayload }) => updateDepartment(id, body),
    onSuccess: invalidate,
  })
}

export function useDeleteDepartment() {
  const invalidate = useOrgInvalidation()
  return useMutation({ mutationFn: deleteDepartment, onSuccess: invalidate })
}

export function useCreateMembership() {
  const invalidate = useOrgInvalidation()
  return useMutation({
    mutationFn: (body: MembershipPayload) => createMembership(body),
    onSuccess: invalidate,
  })
}

export function useUpdateMembership() {
  const invalidate = useOrgInvalidation()
  return useMutation({
    mutationFn: ({ id, isPrimary }: { id: string; isPrimary: boolean }) =>
      updateMembership(id, { is_primary: isPrimary }),
    onSuccess: invalidate,
  })
}

export function useDeleteMembership() {
  const invalidate = useOrgInvalidation()
  return useMutation({ mutationFn: deleteMembership, onSuccess: invalidate })
}
