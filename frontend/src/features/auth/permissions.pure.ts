// 테넌트 역할 기반 판정 — zustand 비의존 순수 함수(`features/rcm/permissions.pure.ts` 와 같은 규약).
import type { UserProfile } from './store'

/** ADR-0031 §2.1 테넌트 역할 5종 중 판정에 쓰는 값. 목록 전체가 필요해지면 그때 넓힌다. */
export const ROLE_ICFR_MANAGER = 'icfr_manager'
/** 관리자 1~3단계(ADR-0038) — 일반·책임·마스터. 작성·검토 요청은 이 중 하나면 된다 */
export const TIER_ROLES = ['icfr_staff', 'icfr_lead', ROLE_ICFR_MANAGER] as const

/**
 * 제도 책임자인가 — 정책 변경·역할 배정 메뉴의 노출 판단.
 *
 * **`can_write` 로 판단하지 말 것.** `can_write` 는 `external_auditor` 인가(조회 전용인가)를
 * 가리는 값이고, `icfr_manager` 판정이 아니다. 일반 사용자는 `can_write=true` 지만
 * 정책을 바꿀 수 없다 — 두 값을 섞으면 **메뉴는 열리는데 서버가 403 을 내는** 상태가 된다.
 * 판정 근거는 `tenant_roles`(= 백엔드 `user_roles`)다.
 *
 * 최종 판정은 서버다(`require_icfr_manager`). 이건 "눌러도 안 되는 것을 미리 아는" 수단이지
 * 우회 수단이 아니다.
 */
export function isIcfrManagerForUser(user: UserProfile | null | undefined): boolean {
  return user?.tenant_roles?.includes(ROLE_ICFR_MANAGER) ?? false
}

/** 회사 전체 평가·증빙을 보는 역할 — 서버 `FULL_VIEW_ROLES`(core/permissions.py)와 같은 집합 */
export const FULL_VIEW_ROLES = [...TIER_ROLES, 'external_auditor', 'auditor', 'external_advisor'] as const

/**
 * 증빙 관리·내 평가 전체 보기(2026-10-16, 조사 4) — 내부회계 관리자 1~3단계·감사인(조회)·외부자문.
 * 통제책임자 등 일반 사용자와 sys_admin 단독 계정은 아니다. 최종 판정은 서버(`require_full_viewer`).
 */
export function canViewAllForUser(user: UserProfile | null | undefined): boolean {
  return FULL_VIEW_ROLES.some((r) => user?.tenant_roles?.includes(r)) ?? false
}

/**
 * 메뉴를 **아예 감출지** — 권한 없는 사람에게 자물쇠로도 보이지 않는다(2026-10-16 Regina: 증빙 관리).
 * 사이드바와 대시보드 카드가 같이 쓴다. `requiresIcfrManager` 는 종전대로 자물쇠 표시다.
 */
export function isNavHidden(item: { requiresFullViewer?: boolean }, user: UserProfile | null | undefined): boolean {
  return Boolean(item.requiresFullViewer) && !canViewAllForUser(user)
}

/** 내부회계 관리자(일반·책임·마스터)인가 — 스코핑 작성 메뉴 노출. 최종 판정은 서버(`require_icfr_staff`). */
export function isIcfrStaffForUser(user: UserProfile | null | undefined): boolean {
  return TIER_ROLES.some((r) => user?.tenant_roles?.includes(r)) ?? false
}
