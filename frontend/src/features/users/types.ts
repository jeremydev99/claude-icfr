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
  /** 직원 초대(ADR-0041) — 아직 본인이 비밀번호를 정하지 않음 / 관리자가 정한 비밀번호라 변경 필요 */
  invite_pending?: boolean
  must_change_password?: boolean
}

/** 생성 결과 — 초대면 설정 링크 원문이 이 응답에서 한 번만 온다 */
export interface UserCreated extends User {
  setup_url?: string | null
  setup_expires_at?: string | null
  /** 메일 발송 결과 — null 이면 메일 설정 없음(링크 직접 전달) */
  mail_sent?: boolean | null
  mail_error?: string | null
}

export interface SetupLink {
  setup_url: string
  expires_at: string
  purpose: 'invite' | 'reset'
  mail_sent?: boolean | null
  mail_error?: string | null
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
  /** 비우면 초대(설정 링크). 넣으면 시스템관리자 비상용 — 다음 로그인 때 변경 강제 */
  password?: string
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

// 배정용 — 관리자 4단계(ADR-0038: 일반·책임·마스터 + 시스템관리자) + ADR-0031 역할. 값은 snake_case 정규값.
// 일반·책임·마스터는 한 사람에 하나만(서버 409), 시스템관리자는 겸직 가능.

export const ROLE_ASSIGN_OPTIONS = [
  { value: 'icfr_staff', label: '일반관리자 (내부회계 담당 직원)' },
  { value: 'icfr_lead', label: '책임관리자 (담당 조직장)' },
  { value: 'icfr_manager', label: '마스터관리자 (내부회계관리자)' },
  { value: 'ceo', label: '대표이사' },
  { value: 'auditor', label: '감사 (상근감사·감사위원회 위원) — 조회 전용' },
  { value: 'external_auditor', label: '외부감사인 — 조회 전용' },
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
  // 외부 사용자 초대(ADR-0039)로만 생기는 역할 — 직접 배정 목록에는 없다(접근 기간·2단계 인증이 함께 걸려야 해서)
  external_advisor: 'PA회계법인 (ICFR 자문)',
  external_specialist: '세무·기장대리인',
}
