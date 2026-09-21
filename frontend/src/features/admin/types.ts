// 부서·소속 도메인 타입 (4-2). 백엔드 `schemas/org.py` 와 1:1.

export interface Department {
  id: string
  name: string
  manager_id: string | null
  /** 계층은 컬럼만 있고 평면 운영이다(ADR-0031 §2.8). 화면에서 다루지 않는다. */
  parent_id: string | null
  /** 인사시스템 연동 키 — 현재 미사용 */
  external_code: string | null
  created_at: string
  updated_at: string
  /** 표시용 파생값 — 화면이 id 로 다시 조회하지 않도록 서버가 채운다 */
  manager_name: string | null
}

export interface DepartmentPayload {
  name: string
  manager_id?: string | null
}

export interface Membership {
  id: string
  user_id: string
  department_id: string
  is_primary: boolean
  created_at: string
  updated_at: string
  user_name: string | null
  department_name: string | null
}

export interface MembershipPayload {
  user_id: string
  department_id: string
  is_primary: boolean
}

export interface ListResponse<T> {
  items: T[]
  total: number
  skip: number
  limit: number
}
