// 상위 3계층(Process/SubProcess/Risk) 편집/삭제 버튼 노출 권한 seam.
// 판정: `/me` 의 can_write + 내부회계관리자(tenant_roles) — 2026-10-08 부터 RCM 바로 반영은 관리자만.
// external_auditor·tenant_roles로 여기서 재판정하지 않는다 — 최종 강제는 서버가 403으로 한다.
import { useAuthStore } from '../auth/store'
import { canEditHierarchyForUser } from './permissions.pure'

export function canEditHierarchy(): boolean {
  return canEditHierarchyForUser(useAuthStore.getState().user)
}
