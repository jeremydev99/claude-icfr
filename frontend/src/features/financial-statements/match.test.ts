import { describe, expect, it } from 'vitest'
import { bulkLinks, filterRows, groupedTemplates, type MatchRow } from './match.pure'

const row = (id: string, extra: Partial<MatchRow> = {}): MatchRow => ({
  account_id: id, name: id, parent_name: null, depth: 0, is_subtotal: false, link: null, suggestion: null, ...extra,
})
const sug = (basis: 'exact' | 'normalized') => ({ template_account_id: `t-${basis}`, template_name: 'T', basis })
const link = { id: 'l', account_id: 'x', template_account_id: 't', template_name: 'T', basis: 'exact' as const, confirmed_at: '', note: null }

describe('template match', () => {
  const rows = [row('a', { suggestion: sug('exact') }), row('b', { suggestion: sug('normalized') }),
    row('c'), row('d', { link, suggestion: sug('exact') })]

  it('일괄 확정은 미연결 + 제안 + 근거(기본 정확일치만)', () => {
    expect(bulkLinks(rows)).toEqual([{ account_id: 'a', template_account_id: 't-exact' }])
    expect(bulkLinks(rows, ['exact', 'normalized']).map((x) => x.account_id)).toEqual(['a', 'b'])
  })
  it('필터', () => {
    expect(filterRows(rows, 'unlinked').map((r) => r.account_id)).toEqual(['a', 'b', 'c'])
    expect(filterRows(rows, 'suggested').map((r) => r.account_id)).toEqual(['a', 'b'])
    expect(filterRows(rows, 'linked').map((r) => r.account_id)).toEqual(['d'])
  })
  it('템플릿 선택지는 그룹 라벨로 묶고 원천 순서대로', () => {
    const g = groupedTemplates([
      { id: '2', name: '대손충당금', group_label: '(1) 당좌자산', sort_order: 2, linked_count: 0 },
      { id: '1', name: '매출채권', group_label: '(1) 당좌자산', sort_order: 1, linked_count: 1 },
      { id: '3', name: '토지', group_label: null, sort_order: 3, linked_count: 0 },
    ])
    expect(g.map(([k, v]) => [k, v.map((x) => x.name)])).toEqual([
      ['(1) 당좌자산', ['매출채권', '대손충당금']], ['(그룹 없음)', ['토지']]])
  })
})
