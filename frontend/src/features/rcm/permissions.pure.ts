// canEditHierarchy 판정 로직만 분리 — zustand store(localStorage 부작용)를 끌어들이지 않아
// jsdom 없이 node 환경에서 단위 테스트 가능하다.
import type { UserProfile } from '../auth/store'
import { isIcfrManagerForUser } from '../auth/permissions.pure'

/**
 * RCM 바로 반영(통제 추가·삭제·상위 계층·어서션·엑셀) — 내부회계관리자만(2026-10-08, 서버 `require_direct_control_edit`).
 * 쓰기 권한이 있어도 관리자가 아니면 버튼을 숨긴다. 통제 필드 수정은 변경 결재(임시저장·상신)로 한다.
 */
export function canEditHierarchyForUser(user: UserProfile | null): boolean {
  return (user?.can_write ?? false) && isIcfrManagerForUser(user)
}
