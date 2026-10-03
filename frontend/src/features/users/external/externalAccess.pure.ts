// 외부 사용자 탭 표시 규칙(ADR-0039) — 화면 판단만. 최종 판정은 서버.

/** 오늘부터 n일 뒤 날짜(YYYY-MM-DD) — 초대 기본 종료일 */
export function addDays(n: number, today = new Date()): string {
  const d = new Date(today.getFullYear(), today.getMonth(), today.getDate() + n)
  const p = (x: number) => String(x).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`
}

/** 접근 상태 칩 — 해지 / 기간 종료 / 곧 종료(14일 이내) / 사용 중 */
export function accessState(
  u: { status: string; valid_from: string; valid_until: string },
  today = addDays(0),
): { label: string; tone: 'muted' | 'warn' | 'ok' | 'bad' } {
  if (u.status !== 'active') return { label: '해지', tone: 'bad' }
  if (today > u.valid_until) return { label: '기간 종료', tone: 'muted' }
  if (today < u.valid_from) return { label: '시작 전', tone: 'muted' }
  if (addDays(14, new Date(today + 'T00:00:00')) >= u.valid_until) return { label: '곧 종료', tone: 'warn' }
  return { label: '사용 중', tone: 'ok' }
}

/** 분기 재확인이 지났는가 — 마지막 재확인이 없거나 90일을 넘으면 true */
export function reviewOverdue(lastReviewedAt: string | null | undefined, now = new Date()): boolean {
  if (!lastReviewedAt) return true
  return now.getTime() - new Date(lastReviewedAt).getTime() > 90 * 86_400_000
}
