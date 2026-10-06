/**
 * 회계연도 규칙 한 곳(2026-10-06, 마스터 "모호한 부분 없도록").
 *
 * - 회사 설정은 **결산월**로 받는다(화면). 저장은 종전대로 시작월(`fiscal_year_start_month` = 결산월 다음 달).
 * - **회계연도 N = N년 시작월 1일에 시작하는 1년**(서버 assessment_period·재무제표 업로드와 같은 규칙).
 *   12월 결산: 2026 회계연도 = 2026.01.01 ~ 2026.12.31 / 3월 결산: 2026 회계연도 = 2026.04.01 ~ 2027.03.31.
 * - 그래서 "2026 회계연도"만 쓰지 않고 **기간을 함께** 보인다(fyLabel).
 */

const pad = (n: number) => String(n).padStart(2, '0')
const lastDay = (y: number, m: number) => new Date(y, m, 0).getDate()

export const endMonthOf = (startMonth: number) => (startMonth === 1 ? 12 : startMonth - 1)
export const startMonthOf = (endMonth: number) => (endMonth === 12 ? 1 : endMonth + 1)

/** 회계연도 기간 — ISO 날짜 */
export function fiscalRange(fy: number, startMonth: number): { start: string; end: string } {
  const em = endMonthOf(startMonth)
  const ey = startMonth === 1 ? fy : fy + 1
  return { start: `${fy}-${pad(startMonth)}-01`, end: `${ey}-${pad(em)}-${pad(lastDay(ey, em))}` }
}

/** "2026.01.01 ~ 2026.12.31" */
export function fiscalRangeText(fy: number, startMonth: number): string {
  const r = fiscalRange(fy, startMonth)
  return `${r.start.replace(/-/g, '.')} ~ ${r.end.replace(/-/g, '.')}`
}

/** "2026 회계연도 (2026.01.01 ~ 2026.12.31)" — 화면 어디서나 이 표기 */
export function fyLabel(fy: number, startMonth: number): string {
  return `${fy} 회계연도 (${fiscalRangeText(fy, startMonth)})`
}

/** 짧은 표기 "2026 회계연도(2026.04~2027.03)" — 좁은 자리용 */
export function fyShort(fy: number, startMonth: number): string {
  const r = fiscalRange(fy, startMonth)
  return `${fy} 회계연도(${r.start.slice(0, 7).replace('-', '.')}~${r.end.slice(0, 7).replace('-', '.')})`
}

/** 회계연도 말일 한국어 "2026년 12월 31일" — 보고서 기준일 */
export function fiscalEndKo(fy: number, startMonth: number): string {
  const [y, m, d] = fiscalRange(fy, startMonth).end.split('-')
  return `${y}년 ${Number(m)}월 ${Number(d)}일`
}

/** 결산월 설명 "12월 결산 · 1월 1일 ~ 12월 31일" / "3월 결산 · 4월 1일 ~ 다음 해 3월 31일" */
export function describeClose(endMonth: number): string {
  const s = startMonthOf(endMonth)
  const ld = lastDay(2025, endMonth) // 2월은 평년 기준(28) — 윤년은 실제 연도로 계산된다
  return s === 1 ? '12월 결산 · 1월 1일 ~ 12월 31일' : `${endMonth}월 결산 · ${s}월 1일 ~ 다음 해 ${endMonth}월 ${ld}일`
}

/** 날짜가 속한 회계연도(서버 current_fiscal_year 와 같다) */
export function fiscalYearOfDate(d: Date, startMonth: number): number {
  return d.getMonth() + 1 >= startMonth ? d.getFullYear() : d.getFullYear() - 1
}
