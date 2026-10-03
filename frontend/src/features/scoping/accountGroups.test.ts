import { describe, expect, it } from 'vitest'
import { groupRows, groupStatus, type GroupRow } from './accountGroups.pure'

const r = (g: string | null, final: string | null, badges: Record<string, string> = {}): GroupRow => ({
  name: `${g}-${final}`, group_label: g, current_amount: 1, change_rate: null, qual_average: null,
  final, snapshot_final: null, badges,
})

describe('groupStatus', () => {
  it('완료 = 전부 판정 + 검토 안 한 값 0', () => {
    expect(groupStatus([r('a', 'Y'), r('a', 'na')], false)).toMatchObject({ complete: true, percent: 100, Y: 1, na: 1 })
    expect(groupStatus([r('a', 'Y', { q1: 'template' })], false)).toMatchObject({ complete: false, pendingRows: 1 })
    expect(groupStatus([r('a', 'Y'), r('a', null)], false)).toMatchObject({ complete: false, percent: 50, unevaluated: 1 })
  })
  it('해당 없음 줄의 템플릿 값은 세지 않는다', () => {
    expect(groupStatus([r('a', 'na', { q1: 'template' })], false).complete).toBe(true)
  })
})

describe('groupRows', () => {
  it('연속한 같은 그룹을 묶고 순서를 지킨다', () => {
    const g = groupRows([r('자산', 'Y'), r('자산', 'N'), r('부채', null), r(null, 'Y')], false)
    expect(g.map((x) => [x.label, x.rows.length])).toEqual([['자산', 2], ['부채', 1], ['기타', 1]])
    expect(g[0].status.complete).toBe(true)
  })
})
