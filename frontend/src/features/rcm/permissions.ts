// 상위 3계층(Process/SubProcess/Risk) 편집/삭제 버튼 노출 권한 seam.
// 판정 소스는 `/me` 응답의 can_write(백엔드 core/permissions.can_write 계산값, ADR-0031) 하나뿐이다.
// external_auditor·tenant_roles로 여기서 재판정하지 않는다 — 최종 강제는 서버가 403으로 한다.
import { useAuthStore } from '../auth/store'
import { canEditHierarchyForUser } from './permissions.pure'

export function canEditHierarchy(): boolean {
  return canEditHierarchyForUser(useAuthStore.getState().user)
}
