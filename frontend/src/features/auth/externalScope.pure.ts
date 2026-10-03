// 외부 사용자 메뉴 범위(ADR-0039 §2.1) — 화면에서 "눌러도 안 되는 메뉴"를 미리 감춘다. 최종 판정은 서버다.
import type { UserProfile } from './store'

/** 모듈 키 → 메뉴 경로. 초대 때 고른 모듈이 이 키로 저장된다 */
export const MODULE_PATHS: Record<string, string> = {
  financial_statements: '/financial-statements',
}

/** 감사위원회·사외이사 — 보고서·현황판·미비점(개선)·알림만 본다 */
const COMMITTEE_PATHS = ['/dashboard', '/report', '/remediation', '/notification']

/**
 * 이 사용자에게 보일 메뉴 경로 목록. `null` 이면 제한 없음(내부 사용자·PA회계법인·외부감사인 —
 * 쓰기 가능 여부는 역할과 `can_write` 가 따로 정한다).
 */
export function allowedPaths(user: UserProfile | null | undefined): string[] | null {
  const ext = user?.external
  if (!ext) return null
  if (ext.user_type === 'committee') return COMMITTEE_PATHS
  if (ext.user_type === 'specialist') {
    return ['/dashboard', '/notification', ...ext.modules.map((m) => MODULE_PATHS[m]).filter(Boolean)]
  }
  return null
}

export function isPathAllowed(user: UserProfile | null | undefined, path: string): boolean {
  const allowed = allowedPaths(user)
  if (allowed === null) return true
  return allowed.some((p) => path === p || path.startsWith(p + '/'))
}

/** 접근 기간 종료까지 남은 날(오늘 포함 아님). 외부 사용자가 아니면 null */
export function daysLeft(user: UserProfile | null | undefined, today = new Date()): number | null {
  const until = user?.external?.valid_until
  if (!until) return null
  const end = new Date(until + 'T23:59:59')
  return Math.max(0, Math.ceil((end.getTime() - today.getTime()) / 86_400_000) - 1)
}
