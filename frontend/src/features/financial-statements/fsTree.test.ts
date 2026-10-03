import { describe, expect, it } from 'vitest'
import { allExpanded, errorsByAccount, flattenStatementOrder, flattenTree, formatAmount, initialExpanded, pathTo, ruleLabel } from './fsTree.pure'
import type { AmountNode } from './types'

const node = (id: string, children: AmountNode[] = [], extra: Partial<AmountNode> = {}): AmountNode => ({
  id, code: null, name: id, statement_type: 'BS', section: 'asset', is_subtotal: children.length > 0,
  rollup_sign: 1, sort_order: 0, depth: 0, has_row: true, amount: '0', raw_row_no: null, raw_label: null,
  raw_indent: null, raw_value: null, raw_meta: null, children, ...extra,
})

describe('formatAmount', () => {
  it('문자열 그대로 천 단위 구분, 음수는 괄호, 소수 0 제거', () => {
    expect(formatAmount('72078938796.00')).toBe('72,078,938,796')
    expect(formatAmount('-9572352.00')).toBe('(9,572,352)')
    expect(formatAmount('0.00')).toBe('0')
    expect(formatAmount('-0.00')).toBe('0')
    expect(formatAmount('1234.50')).toBe('1,234.5')
    expect(formatAmount(null)).toBe('—')
  })
  it('부동소수로 바꾸지 않는다 — 20자리도 그대로', () => {
    expect(formatAmount('123456789012345678.00')).toBe('123,456,789,012,345,678')
  })
})

describe('tree', () => {
  const tree = [node('A', [node('CA', [node('cash'), node('ar')]), node('NCA', [node('ppe')])]),
    node('L', [node('ap')])]

  it('처음엔 깊이 1 까지 펼친다', () => {
    const ex = initialExpanded(tree, 1)
    expect([...ex].sort()).toEqual(['A', 'L'])
    expect(flattenTree(tree, ex).map((r) => r.node.id)).toEqual(['A', 'CA', 'NCA', 'L', 'ap'])
  })
  it('모두 펼치기 · 깊이', () => {
    const rows = flattenTree(tree, allExpanded(tree))
    expect(rows.map((r) => `${r.node.id}:${r.depth}`)).toEqual(
      ['A:0', 'CA:1', 'cash:2', 'ar:2', 'NCA:1', 'ppe:2', 'L:0', 'ap:1'])
  })
  it('검증 오류 계정까지 조상 경로', () => {
    expect(pathTo(tree, 'ar')).toEqual(['A', 'CA'])
    expect(pathTo(tree, 'nope')).toBeNull()
  })
  it('임시계정 행 표시', () => {
    const t = [node('P', [node('s', [], { raw_meta: { suspense: true } })])]
    expect(flattenTree(t, allExpanded(t))[1].isSuspense).toBe(true)
  })
})

describe('validation', () => {
  it('계정별로 묶고 계정 없는 오류는 null 키', () => {
    const m = errorsByAccount([
      { rule: 'subtotal', account_id: 'a', account_code: null, account_name: 'A', expected: '1', actual: '2', diff: '1' },
      { rule: 'balance', account_id: null, account_code: null, account_name: null, expected: '1', actual: '2', diff: '1' },
    ])
    expect(m.get('a')?.length).toBe(1)
    expect(m.get(null)?.[0].rule).toBe('balance')
    expect(ruleLabel('suspense_unresolved')).toContain('임시계정')
    expect(ruleLabel('unknown_rule')).toBe('unknown_rule')
  })
})

describe('reclass targets', () => {
  it('같은 소계 아래 형제만, 임시계정 제외', async () => {
    const { reclassTargets } = await import('./fsTree.pure')
    const t = [node('P', [node('a'), node('b'), node('s', [], { raw_meta: { suspense: true } })]), node('Q')]
    expect(reclassTargets(t, 'P').map((n) => n.id)).toEqual(['a', 'b'])
    expect(reclassTargets(t, 'none')).toEqual([])
  })
})

describe('flattenStatementOrder — 공시 순서', () => {
  const n = (id: string, children: AmountNode[] = [], rollup_sign = 1): AmountNode => ({
    id, code: null, name: id, statement_type: 'PL', section: 'pl', is_subtotal: children.length > 0, rollup_sign,
    sort_order: 0, depth: 0, has_row: true, amount: '1', raw_row_no: null, raw_label: null, raw_indent: null,
    raw_value: null, raw_meta: null, children,
  })
  const pl = [n('총포괄', [
    n('순이익', [
      n('세전', [n('영업이익', [n('영업수익', [n('수입수수료'), n('용역매출')]), n('영업비용', [n('급여')], -1)]), n('금융손익')]),
      n('법인세', [n('법인세등')], -1),
    ]),
    n('기타포괄', [n('재분류안됨')]),
  ])]

  it('매출부터 위→아래, 결과 행은 구성 항목 아래', () => {
    const rows = flattenStatementOrder(pl, new Set(['영업수익']))
    expect(rows.map((r) => r.node.id)).toEqual([
      '영업수익', '수입수수료', '용역매출', '영업비용', '영업이익', '금융손익', '세전', '법인세', '순이익', '기타포괄', '총포괄',
    ])
    expect(rows.filter((r) => r.isResult).map((r) => r.node.id)).toEqual(['영업이익', '세전', '순이익', '총포괄'])
    expect(rows.find((r) => r.node.id === '수입수수료')?.depth).toBe(1)
    expect(rows.find((r) => r.node.id === '총포괄')?.depth).toBe(0)
  })

  it('빼는 하위가 없는 트리(재무상태표 등)는 기존 순서와 같다', () => {
    const bs = [n('자산', [n('유동', [n('현금')]), n('비유동')])]
    const all = new Set(['자산', '유동'])
    expect(flattenStatementOrder(bs, all).map((r) => r.node.id)).toEqual(flattenTree(bs, all).map((r) => r.node.id))
  })
})
