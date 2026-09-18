// 테넌트 역할 기반 판정 — zustand 비의존 순수 함수(`features/rcm/permissions.pure.ts` 와 같은 규약).
import type { UserProfile } from './store'

/** ADR-0031 §2.1 테넌트 역할 5종 중 판정에 쓰는 값. 목록 전체가 필요해지면 그때 넓힌다. */
export const ROLE_ICFR_MANAGER = 'icfr_manager'

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
