/**
 * 일정관리 (초안) — 순수 로직.
 *
 * 전용 일정 백엔드가 없으므로 **표준 ICFR 연간 일정 템플릿**을 데이터로 둔다.
 * 월은 "회계월 오프셋"으로 적는다 — 1 = 회계연도 첫 달, 12 = 마지막 달,
 * 13~15 = 익년(결산 후) 1~3개월. 회계연도 시작월 정책(fiscal_year_start_month)에 따라
 * 달력 월로 변환한다. 회계연도 FY 는 date(FY, 시작월, 1) 에 시작한다(백엔드 assessment_period 와 같은 규칙).
 */

export const TOTAL_COLUMNS = 15 // 회계연도 12개월 + 익년 3개월

export type PhaseCategory = 'planning' | 'design' | 'operation' | 'remediation' | 'reporting' | 'audit'

export interface SchedulePhase {
  id: string
  name: string
  category: PhaseCategory
  /** 회계월 오프셋 (1-based, 13 이상 = 익년) */
  start: number
  end: number
  description: string
  tasks: string[]
}

export const STANDARD_TEMPLATE: SchedulePhase[] = [
  {
    id: 'scoping',
    name: '스코핑·중요성 결정',
    category: 'planning',
    start: 1,
    end: 2,
    description: '전기 재무제표 기준 중요성 금액 산정, 유의한 계정·프로세스·사업단위 선정',
    tasks: ['중요성 금액 산정', '유의한 계정과목·주석 선정', '평가 범위(사업단위·프로세스) 확정'],
  },
  {
    id: 'rcm',
    name: 'RCM 갱신',
    category: 'planning',
    start: 2,
    end: 3,
    description: '프로세스 변경 반영, 위험·통제 매트릭스 개정 및 승인',
    tasks: ['프로세스 변경사항 수집', '위험·통제 추가/폐기 반영', 'RCM 개정 승인'],
  },
  {
    id: 'design',
    name: '설계평가',
    category: 'design',
    start: 3,
    end: 5,
    description: '핵심통제 설계의 적정성 검토(워크스루)',
    tasks: ['설계평가 회차 생성', '통제별 워크스루·설계평가 기록', '설계 미비점 식별'],
  },
  {
    id: 'op-interim',
    name: '운영평가 (중간)',
    category: 'operation',
    start: 6,
    end: 8,
    description: '상반기 표본 기준 운영 효과성 테스트',
    tasks: ['운영평가(중간) 회차 생성', '표본 추출·증빙 수집', '테스트 결과 기록·승인'],
  },
  {
    id: 'op-final',
    name: '운영평가 (기말)',
    category: 'operation',
    start: 10,
    end: 13,
    description: '잔여기간(Roll-forward) 및 기말 결산 통제 테스트',
    tasks: ['운영평가(기말) 회차 생성', 'Roll-forward 테스트', '기말 결산통제(FCRP) 테스트'],
  },
  {
    id: 'remediation',
    name: '미비점 개선·재테스트',
    category: 'remediation',
    start: 4,
    end: 13,
    description: '식별된 미비점의 개선계획 수립·이행 및 재테스트 (연중 상시, 기말 집중)',
    tasks: ['미비점 개선계획 이행 점검', '개선 완료 통제 재테스트'],
  },
  {
    id: 'reporting',
    name: '경영진 운영실태 보고·이사회/감사위원회 보고',
    category: 'reporting',
    start: 14,
    end: 15,
    description: '대표이사 운영실태 보고, 감사(위원회) 평가보고, 이사회 보고',
    tasks: ['운영실태 보고서 작성', '감사위원회 평가보고', '이사회 보고'],
  },
  {
    id: 'audit',
    name: '외부감사인 대응',
    category: 'audit',
    start: 12,
    end: 15,
    description: '외부감사인 내부회계관리제도 감사 자료 요청 대응',
    tasks: ['감사인 PBC 자료 대응', '감사인 발견사항 협의'],
  },
]

export interface MonthColumn {
  offset: number // 1..TOTAL_COLUMNS
  year: number
  month: number // 1..12
  label: string // "3월" 등
  nextYear: boolean // 회계연도 종료 후(익년) 여부
}

export function normalizeStartMonth(v: unknown): number {
  const n = typeof v === 'number' ? v : parseInt(String(v ?? ''), 10)
  return Number.isInteger(n) && n >= 1 && n <= 12 ? n : 1
}

/** GET /api/org/policies 응답 items 에서 회계연도 시작월을 꺼낸다. 없으면 1. */
export function startMonthFromPolicies(
  items: { policy_key: string; policy_value: string }[] | undefined,
): number {
  const p = items?.find((i) => i.policy_key === 'fiscal_year_start_month')
  return normalizeStartMonth(p?.policy_value)
}

export function currentFiscalYear(today: Date, startMonth: number): number {
  const m = today.getMonth() + 1
  return m >= startMonth ? today.getFullYear() : today.getFullYear() - 1
}

export function offsetToCalendar(fy: number, startMonth: number, offset: number): { year: number; month: number } {
  const idx = startMonth - 1 + (offset - 1)
  return { year: fy + Math.floor(idx / 12), month: (idx % 12) + 1 }
}

/** 달력 (year, month) → 회계월 오프셋. 범위를 벗어나도 그대로 반환(음수·16 이상 가능). */
export function calendarToOffset(fy: number, startMonth: number, year: number, month: number): number {
  return (year - fy) * 12 + (month - startMonth) + 1
}

export function buildColumns(fy: number, startMonth: number): MonthColumn[] {
  return Array.from({ length: TOTAL_COLUMNS }, (_, i) => {
    const offset = i + 1
    const { year, month } = offsetToCalendar(fy, startMonth, offset)
    return { offset, year, month, label: `${month}월`, nextYear: offset > 12 }
  })
}

export function formatOffsetRange(fy: number, startMonth: number, start: number, end: number): string {
  const s = offsetToCalendar(fy, startMonth, start)
  const e = offsetToCalendar(fy, startMonth, end)
  const fmt = (c: { year: number; month: number }) => `${c.year}.${String(c.month).padStart(2, '0')}`
  return start === end ? fmt(s) : `${fmt(s)} ~ ${fmt(e)}`
}

/** 오늘이 이 회계연도 그리드 안에 있으면 그 오프셋, 아니면 null. */
export function todayOffset(fy: number, startMonth: number, today: Date): number | null {
  const o = calendarToOffset(fy, startMonth, today.getFullYear(), today.getMonth() + 1)
  return o >= 1 && o <= TOTAL_COLUMNS ? o : null
}

/** 해당 오프셋에 진행 중인 단계. */
export function phasesAt(offset: number | null, template: SchedulePhase[] = STANDARD_TEMPLATE): SchedulePhase[] {
  if (offset == null) return []
  return template.filter((p) => p.start <= offset && offset <= p.end)
}

/** 다음 달에 시작하는 단계 (준비용). */
export function phasesStartingAt(offset: number | null, template: SchedulePhase[] = STANDARD_TEMPLATE): SchedulePhase[] {
  if (offset == null) return []
  return template.filter((p) => p.start === offset)
}

/** "YYYY-MM-DD" 기간을 그리드 오프셋 범위로. 그리드와 겹치지 않으면 null, 겹치면 잘라서 반환. */
export function periodToSpan(
  fy: number,
  startMonth: number,
  periodStart: string,
  periodEnd: string,
): { start: number; end: number } | null {
  const parse = (s: string) => {
    const [y, m] = s.split('-').map((x) => parseInt(x, 10))
    return { y, m }
  }
  const a = parse(periodStart)
  const b = parse(periodEnd)
  if (!a.y || !a.m || !b.y || !b.m) return null
  const s = calendarToOffset(fy, startMonth, a.y, a.m)
  const e = calendarToOffset(fy, startMonth, b.y, b.m)
  if (e < 1 || s > TOTAL_COLUMNS || e < s) return null
  return { start: Math.max(1, s), end: Math.min(TOTAL_COLUMNS, e) }
}

export const CATEGORY_STYLE: Record<PhaseCategory, string> = {
  planning: 'bg-sky-500/80',
  design: 'bg-indigo-500/80',
  operation: 'bg-emerald-500/80',
  remediation: 'bg-amber-500/70',
  reporting: 'bg-rose-500/80',
  audit: 'bg-slate-500/80',
}

export const KIND_LABEL: Record<string, string> = { design: '설계평가', operation: '운영평가' }
export const STATUS_LABEL: Record<string, string> = { open: '진행 중', closed: '마감', approved: '승인' }
export const FREQ_LABEL: Record<string, string> = {
  weekly: '주별',
  monthly: '월별',
  quarterly: '분기',
  semiannual: '반기',
  annual: '연간',
}

// ── 일정안(2026-10-06) — 날짜 항목을 월 그리드 단계로 ─────────────────
export interface DatedItem {
  id: string
  title: string
  category: string
  start_date: string
  end_date: string
  description: string | null
  tasks: string[]
}

/** 일정안 항목 → 그리드 단계(월 단위). 그리드 밖 항목은 뺀다. 분류를 모르면 'audit' 색(회색)으로 */
export function itemsToPhases(items: DatedItem[], fy: number, startMonth: number): (SchedulePhase & { itemId: string })[] {
  const out: (SchedulePhase & { itemId: string })[] = []
  for (const it of items) {
    const span = periodToSpan(fy, startMonth, it.start_date, it.end_date)
    if (!span) continue
    const category = (['planning', 'design', 'operation', 'remediation', 'reporting', 'audit'].includes(it.category)
      ? it.category : 'audit') as PhaseCategory
    out.push({ id: it.id, itemId: it.id, name: it.title, category, start: span.start, end: span.end,
      description: it.description ?? '', tasks: it.tasks ?? [] })
  }
  return out
}

export const CATEGORY_LABEL: Record<string, string> = {
  planning: '계획', design: '설계평가', operation: '운영평가', remediation: '개선', reporting: '보고', audit: '외부감사', other: '기타',
}

// ── 간트 일 단위 위치(2026-10-07, 13.9-100) — 막대 끌기·양 끝 늘이기 ─────────────
// 머리의 월 칸은 폭이 같으므로 x 는 "몇 번째 달 + 그 달 안의 몇 번째 날" 비율이다(달마다 날 수가 달라도 칸과 맞는다).
const dim = (y: number, m: number) => new Date(Date.UTC(y, m, 0)).getUTCDate()
const iso = (y: number, m: number, d: number) => `${y}-${String(m).padStart(2, '0')}-${String(d).padStart(2, '0')}`

/** 날짜(그날 시작) → 0..1 (그리드 왼쪽 끝 = 0, 15번째 달 끝 = 1). 범위 밖은 0·1 로 자른다 */
export function dateToX(fy: number, startMonth: number, date: string): number {
  const [y, m, d] = date.split('-').map((x) => parseInt(x, 10))
  const off = calendarToOffset(fy, startMonth, y, m) - 1
  const x = (off + (d - 1) / dim(y, m)) / TOTAL_COLUMNS
  return Math.min(1, Math.max(0, x))
}

/** 날짜 끝(그날 마지막) → 0..1 — 막대 오른쪽 끝 */
export function dateEndX(fy: number, startMonth: number, date: string): number {
  const [y, m, d] = date.split('-').map((x) => parseInt(x, 10))
  const off = calendarToOffset(fy, startMonth, y, m) - 1
  return Math.min(1, Math.max(0, (off + d / dim(y, m)) / TOTAL_COLUMNS))
}

/** 0..1 → 그 위치의 날짜(일 단위로 맞춘다) */
export function xToDate(fy: number, startMonth: number, x: number): string {
  const c = Math.min(TOTAL_COLUMNS - 1e-9, Math.max(0, x * TOTAL_COLUMNS))
  const off = Math.floor(c)
  const { year, month } = offsetToCalendar(fy, startMonth, off + 1)
  const n = dim(year, month)
  return iso(year, month, Math.min(n, Math.floor((c - off) * n) + 1))
}

/** 날짜 + n일 */
export function addDays(date: string, n: number): string {
  const [y, m, d] = date.split('-').map((x) => parseInt(x, 10))
  const t = new Date(Date.UTC(y, m - 1, d + n))
  return iso(t.getUTCFullYear(), t.getUTCMonth() + 1, t.getUTCDate())
}

/** 두 날짜 사이 일수(b - a) */
export function daysBetween(a: string, b: string): number {
  const p = (s: string) => { const [y, m, d] = s.split('-').map((x) => parseInt(x, 10)); return Date.UTC(y, m - 1, d) }
  return Math.round((p(b) - p(a)) / 86400000)
}

export type DragMode = 'move' | 'start' | 'end'

/** 끌기 결과 — 옮기기는 기간 길이 유지, 양 끝은 반대쪽을 넘지 못한다 */
export function dragDates(mode: DragMode, start: string, end: string, grab: string, now: string): { start: string; end: string } {
  if (mode === 'move') {
    const n = daysBetween(grab, now)
    return { start: addDays(start, n), end: addDays(end, n) }
  }
  if (mode === 'start') return { start: daysBetween(now, end) < 0 ? end : now, end }
  return { start, end: daysBetween(start, now) < 0 ? start : now }
}

/** 표준 일정(월 오프셋) → 날짜 기간 — 승인본·일정안이 없을 때 같은 막대로 그리기 위함 */
export function offsetsToDates(fy: number, startMonth: number, s: number, e: number): { start: string; end: string } {
  const a = offsetToCalendar(fy, startMonth, s)
  const b = offsetToCalendar(fy, startMonth, e)
  return { start: iso(a.year, a.month, 1), end: iso(b.year, b.month, dim(b.year, b.month)) }
}

/** 작성 중 판과 승인본 비교 — 항목 id 기준. 화면 표시(바뀜·추가)와 '승인 대기 변경 n건' 안내용 */
export function planChanges(items: DatedItem[], approved: DatedItem[] | null): { changed: Set<string>; added: Set<string>; removed: DatedItem[] } {
  const changed = new Set<string>()
  const added = new Set<string>()
  if (!approved) return { changed, added, removed: [] }
  const byId = new Map(approved.map((a) => [a.id, a]))
  for (const it of items) {
    const a = byId.get(it.id)
    if (!a) added.add(it.id)
    else if (a.start_date !== it.start_date || a.end_date !== it.end_date || a.title !== it.title) changed.add(it.id)
  }
  const ids = new Set(items.map((i) => i.id))
  return { changed, added, removed: approved.filter((a) => !ids.has(a.id)) }
}
