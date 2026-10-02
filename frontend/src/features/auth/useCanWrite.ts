// 쓰기 버튼 노출 판정 — `/me` 의 can_write(백엔드 `require_write` 와 같은 판정, ADR-0031 §2.1).
// false 는 external_auditor(조회 전용)다. 화면은 숨기기만 하고 최종 강제는 서버 403 이다.
import { useAuthStore } from './store'

export function useCanWrite(): boolean {
  return useAuthStore((s) => s.user?.can_write ?? false)
}
