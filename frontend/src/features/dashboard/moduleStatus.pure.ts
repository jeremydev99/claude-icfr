import type { ModuleStatus } from '@/config/navigation'

/**
 * 대시보드 카드 배지 — `navigation.ts` 의 고정 상태를 **실제 데이터 건수**로 보정한다(2026-09-30).
 * 고정값만 쓰면 데이터가 들어와도 "데이터 없음"으로 남았다(스코핑 1,897개 값이 있는데 데이터 없음).
 * 건수가 1 이상이면 화면이 있는 모듈(ready·api·draft)은 `live` 로 올린다. 준비중(todo)은 그대로 둔다.
 */
export function effectiveStatus(base: ModuleStatus, count: number | undefined): ModuleStatus {
  if (base === 'todo') return 'todo'
  return count && count > 0 ? 'live' : base
}
