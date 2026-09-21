import apiClient from '@/lib/axios'
import type {
  Department,
  DepartmentPayload,
  ListResponse,
  Membership,
  MembershipPayload,
} from '../types'

export async function fetchDepartments(): Promise<ListResponse<Department>> {
  const res = await apiClient.get<ListResponse<Department>>('/api/org/departments', {
    params: { limit: 200 },
  })
  return res.data
}

export async function createDepartment(body: DepartmentPayload): Promise<Department> {
  const res = await apiClient.post<Department>('/api/org/departments', body)
  return res.data
}

export async function updateDepartment(id: string, body: DepartmentPayload): Promise<Department> {
  const res = await apiClient.patch<Department>(`/api/org/departments/${id}`, body)
  return res.data
}

export async function deleteDepartment(id: string): Promise<void> {
  await apiClient.delete(`/api/org/departments/${id}`)
}

/**
 * 소속 목록. 부서를 지정하면 그 부서만, 없으면 테넌트 전체.
 *
 * 전체를 받는 쓰임이 하나 있다 — **주 소속을 옮기기 전에 "어디서 옮겨지는지"를 보여주려면**
 * 그 사람의 현재 주 소속을 알아야 한다.
 */
export async function fetchMemberships(
  params: { department_id?: string } = {},
): Promise<ListResponse<Membership>> {
  const res = await apiClient.get<ListResponse<Membership>>('/api/org/memberships', {
    params: { limit: 500, ...params },
  })
  return res.data
}

export async function createMembership(body: MembershipPayload): Promise<Membership> {
  const res = await apiClient.post<Membership>('/api/org/memberships', body)
  return res.data
}

export async function updateMembership(
  id: string,
  body: { is_primary: boolean },
): Promise<Membership> {
  const res = await apiClient.patch<Membership>(`/api/org/memberships/${id}`, body)
  return res.data
}

export async function deleteMembership(id: string): Promise<void> {
  await apiClient.delete(`/api/org/memberships/${id}`)
}
