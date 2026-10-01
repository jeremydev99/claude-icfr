export interface User {
  id: string
  email: string
  display_name: string
  role: string
  is_active: boolean
  created_at: string
  /** 보안 1단계 — 연속 실패 횟수·잠금 해제 시각 */
  failed_login_count?: number
  locked_until?: string | null
}

export interface LoginEvent {
  id: string
  user_id: string | null
  email: string
  success: boolean
  reason: string
  ip: string | null
  user_agent: string | null
  created_at: string
}

export interface UserListResponse {
  items: User[]
  total: number
  skip: number
  limit: number
}

export interface UserRole {
  id: string
  user_id: string
  role_name: string
  scope: string | null
  created_at: string
  updated_at: string
}

export interface UserRoleListResponse {
  items: UserRole[]
  total: number
  skip: number
  limit: number
}

export interface UserCreatePayload {
  email: string
  password: string
  display_name: string
  role: string
}

export interface UserUpdatePayload {
  display_name?: string
  role?: string
  is_active?: boolean
}

export interface ResetPasswordPayload {
  new_password: string
}

export interface UserRoleCreatePayload {
  user_id: string
  role_name: string
  scope?: string | null
}

export interface UserRoleUpdatePayload {
  role_name?: string
  scope?: string | null
}

export const ROLE_NAME_OPTIONS = [
  { value: 'Administrator', label: '관리자' },
  { value: 'ProcessOwner', label: '프로세스 책임자' },
  { value: 'ControlOwner', label: '통제 수행자' },
  { value: 'Tester', label: '평가자' },
  { value: 'Reviewer', label: '검토자' },
  { value: 'ExternalAuditor', label: '외부감사인' },
  { value: 'Executive', label: '경영진' },
] as const
