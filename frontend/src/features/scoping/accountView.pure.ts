/**
 * 계정 평가 표 보기(필터·정렬) — 순수 함수, `accountView.test.ts`.
 * **저장하지 않는다**: 화면 상태로만 두어 새로고침하면 원래 순서·전체 보기로 돌아간다(2026-10-03 마스터).
 */
export type AccountFilter = 'all' | 'Y' | 'N' | 'unevaluated' | 'na' | 'pending'
export type AccountSort = 'default' | 'amount_desc' | 'amount_asc' | 'change_desc' | 'qual_desc' | 'name'

export const FILTER_LABELS: Record<AccountFilter, string> = {
  all: '전체', Y: '유의(Y)만', N: '비유의(N)만', unevaluated: '미평가만', na: '해당 없음만',
  pending: '검토 안 한 템플릿 값 있는 줄',
}
export const SORT_LABELS: Record<AccountSort, string> = {
  default: '원래 순서(재무제표 순)', amount_desc: '기준 금액 큰 순', amount_asc: '기준 금액 작은 순',
  change_desc: '증감률 큰 순(절대값)', qual_desc: '질적 평균 높은 순', name: '계정명 가나다순',
}

export interface ViewRow {
  name: string
  current_amount: number | null
  change_rate: string | null
  qual_average: string | null
  final: string | null
  snapshot_final?: string | null
  badges: Record<string, string>
}

/** 확정 상태면 확정 당시 결론(스냅샷)으로 거른다 — 표의 결론 칸과 같은 기준 */
export function conclusionOf(r: ViewRow, confirmed: boolean): string | null {
  return confirmed ? (r.snapshot_final ?? null) : r.final
}

export function filterRows<T extends ViewRow>(rows: T[], f: AccountFilter, confirmed: boolean): T[] {
  switch (f) {
    case 'Y': return rows.filter((r) => conclusionOf(r, confirmed) === 'Y')
    case 'N': return rows.filter((r) => conclusionOf(r, confirmed) === 'N')
    case 'unevaluated': return rows.filter((r) => { const c = conclusionOf(r, confirmed); return c !== 'Y' && c !== 'N' && c !== 'na' })
    case 'na': return rows.filter((r) => conclusionOf(r, confirmed) === 'na')
    case 'pending': return rows.filter((r) => conclusionOf(r, confirmed) !== 'na' && Object.values(r.badges).includes('template'))
    default: return rows
  }
}

const num = (v: string | number | null | undefined): number | null => {
  if (v === null || v === undefined || v === '') return null
  const n = typeof v === 'number' ? v : Number(v)
  return Number.isFinite(n) ? n : null
}

/** 값이 없는 줄은 어떤 정렬에서도 맨 아래 — 비어 있는 것을 위로 올리지 않는다 */
function byNumber<T>(rows: T[], get: (r: T) => number | null, desc: boolean): T[] {
  return [...rows].sort((a, b) => {
    const x = get(a), y = get(b)
    if (x === null && y === null) return 0
    if (x === null) return 1
    if (y === null) return -1
    return desc ? y - x : x - y
  })
}

export function sortRows<T extends ViewRow>(rows: T[], s: AccountSort): T[] {
  switch (s) {
    case 'amount_desc': return byNumber(rows, (r) => num(r.current_amount), true)
    case 'amount_asc': return byNumber(rows, (r) => num(r.current_amount), false)
    case 'change_desc': return byNumber(rows, (r) => { const n = num(r.change_rate); return n === null ? null : Math.abs(n) }, true)
    case 'qual_desc': return byNumber(rows, (r) => num(r.qual_average), true)
    case 'name': return [...rows].sort((a, b) => a.name.localeCompare(b.name, 'ko'))
    default: return rows
  }
}
