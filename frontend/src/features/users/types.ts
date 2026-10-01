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

// 배정용 — 신규 5역할(ADR-0031)만 선택 가능. 값은 snake_case 정규값.

export const ROLE_ASSIGN_OPTIONS = [
  { value: 'icfr_manager', label: '내부회계관리자' },
  { value: 'ceo', label: '대표자' },
  { value: 'auditor', label: '감사' },
  { value: 'external_auditor', label: '외부감사인' },
  { value: 'sys_admin', label: '시스템관리자' },
] as const

// 표시용 — 구7종(기존 라벨 유지) + 신규5역할 전체.
export const ROLE_LABELS: Record<string, string> = {
  Administrator: '관리자',
  ProcessOwner: '프로세스 책임자',
  ControlOwner: '통제 수행자',
  Tester: '평가자',
  Reviewer: '검토자',
  ExternalAuditor: '외부감사인',
  Executive: '경영진',
  ...Object.fromEntries(ROLE_ASSIGN_OPTIONS.map((o) => [o.value, o.label])),
}
