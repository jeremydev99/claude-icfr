import { describe, expect, it } from 'vitest'
import { filterRows, sortRows, type ViewRow } from './accountView.pure'

const r = (name: string, amt: number | null, final: string | null, extra: Partial<ViewRow> = {}): ViewRow => ({
  name, current_amount: amt, change_rate: null, qual_average: null, final, snapshot_final: null, badges: {}, ...extra,
})
const rows = [r('나', 100, 'Y'), r('가', null, null), r('다', 300, 'N', { change_rate: '-0.9' }), r('라', 50, 'Y', { change_rate: '0.2' })]

describe('filterRows', () => {
  it('유의·비유의·미평가', () => {
    expect(filterRows(rows, 'Y', false).map((x) => x.name)).toEqual(['나', '라'])
    expect(filterRows(rows, 'N', false).map((x) => x.name)).toEqual(['다'])
    expect(filterRows(rows, 'unevaluated', false).map((x) => x.name)).toEqual(['가'])
  })
  it('확정 상태는 스냅샷 결론으로', () => {
    expect(filterRows([r('a', 1, 'N', { snapshot_final: 'Y' })], 'Y', true)).toHaveLength(1)
  })
  it('검토 안 한 템플릿 값', () => {
    expect(filterRows([r('a', 1, 'Y', { badges: { q1: 'template' } }), r('b', 1, 'Y')], 'pending', false)).toHaveLength(1)
  })
})

describe('sortRows', () => {
  it('금액 큰 순 — 빈 값은 맨 아래, 원본은 바꾸지 않는다', () => {
    expect(sortRows(rows, 'amount_desc').map((x) => x.name)).toEqual(['다', '나', '라', '가'])
    expect(rows[0].name).toBe('나')
  })
  it('증감률 절대값·이름', () => {
    expect(sortRows(rows, 'change_desc').map((x) => x.name).slice(0, 2)).toEqual(['다', '라'])
    expect(sortRows(rows, 'name').map((x) => x.name)).toEqual(['가', '나', '다', '라'])
    expect(sortRows(rows, 'default')).toBe(rows)
  })
})
