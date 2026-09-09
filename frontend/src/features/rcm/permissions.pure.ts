// canEditHierarchy 판정 로직만 분리 — zustand store(localStorage 부작용)를 끌어들이지 않아
// jsdom 없이 node 환경에서 단위 테스트 가능하다.
import type { UserProfile } from '../auth/store'

export function canEditHierarchyForUser(user: UserProfile | null): boolean {
  return user?.can_write ?? false
}
