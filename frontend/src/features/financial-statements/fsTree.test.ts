import { describe, expect, it } from 'vitest'
import { allExpanded, errorsByAccount, flattenTree, formatAmount, initialExpanded, pathTo, ruleLabel } from './fsTree.pure'
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
