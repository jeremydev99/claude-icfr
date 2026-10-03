/**
 * 재무제표 화면 순수 로직 (8-D) — DOM·네트워크 없음. 단위 테스트 대상(`fsTree.test.ts`).
 */
import type { AmountNode, ValidationItem } from './types'

/**
 * 금액 문자열("-1234567.00") → 표시("(1,234,567)"). **부동소수로 바꾸지 않는다** — 20자리 금액이 깨진다.
 * 음수는 공시 관행대로 괄호. 소수부가 0 이면 떼고, 아니면 그대로 둔다. null 은 "—"(0 과 구분).
 */
export function formatAmount(v: string | null | undefined): string {
  if (v === null || v === undefined || v === '') return '—'
  let s = String(v).trim()
  const neg = s.startsWith('-')
  if (neg) s = s.slice(1)
  const [intPart, frac = ''] = s.split('.')
  const grouped = intPart.replace(/^0+(?=\d)/, '').replace(/\B(?=(\d{3})+(?!\d))/g, ',')
  const fracTrim = frac.replace(/0+$/, '')
  const body = fracTrim ? `${grouped}.${fracTrim}` : grouped
  if (neg && body !== '0') return `(${body})`
  return body
}

export interface FlatRow {
  node: AmountNode
  depth: number
  hasChildren: boolean
  expanded: boolean
  isSuspense: boolean
}

export const isSuspenseNode = (n: AmountNode) =>
  Boolean(n.raw_meta && (n.raw_meta as Record<string, unknown>).suspense)

/** 펼친 노드만 따라 내려가며 표 행으로 편다. `expanded` 에 없는 노드는 접힌 것이다. */
export function flattenTree(nodes: AmountNode[], expanded: Set<string>, depth = 0, out: FlatRow[] = []): FlatRow[] {
  for (const n of nodes) {
    const hasChildren = n.children.length > 0
    const open = expanded.has(n.id)
    out.push({ node: n, depth, hasChildren, expanded: open, isSuspense: isSuspenseNode(n) })
    if (hasChildren && open) flattenTree(n.children, expanded, depth + 1, out)
  }
  return out
}

/** 처음 펼침 상태 — `maxDepth` 까지 자식 있는 노드를 모두 펼친다. */
export function initialExpanded(nodes: AmountNode[], maxDepth = 1, depth = 0, out = new Set<string>()): Set<string> {
  for (const n of nodes) {
    if (n.children.length && depth < maxDepth) {
      out.add(n.id)
      initialExpanded(n.children, maxDepth, depth + 1, out)
    }
  }
  return out
}

/** 계정 id 까지의 조상 id — 검증 오류를 누르면 그 행이 보이도록 펼친다. 못 찾으면 null. */
export function pathTo(nodes: AmountNode[], id: string, trail: string[] = []): string[] | null {
  for (const n of nodes) {
    if (n.id === id) return trail
    const got = pathTo(n.children, id, [...trail, n.id])
    if (got) return got
  }
  return null
}

/** 모든 노드를 펼친 id 집합 */
export function allExpanded(nodes: AmountNode[], out = new Set<string>()): Set<string> {
  for (const n of nodes) {
    if (n.children.length) {
      out.add(n.id)
      allExpanded(n.children, out)
    }
  }
  return out
}

/** 검증 오류를 계정별로 묶는다(행에 표시). 계정 없는 오류(균형 등)는 `null` 키. */
export function errorsByAccount(items: ValidationItem[]): Map<string | null, ValidationItem[]> {
  const m = new Map<string | null, ValidationItem[]>()
  for (const e of items) {
    const k = e.account_id ?? null
    m.set(k, [...(m.get(k) ?? []), e])
  }
  return m
}

/** 검증 규칙 코드 → 사람이 읽는 말. 모르는 코드는 그대로. */
export const RULE_LABELS: Record<string, string> = {
  balance: '자산 = 부채 + 자본 불일치',
  balance_missing_section: '자산 또는 부채·자본 측이 없음',
  subtotal: '소계 ≠ 하위 합',
  subtotal_no_children: '소계인데 하위 계정이 없음',
  subtotal_amount_missing: '소계 금액이 비어 있음(검사 생략)',
  suspense_unresolved: '임시계정(원본 차이) 미해결',
  invalid_unit: '단위가 올바르지 않음',
  invalid_section: '섹션이 올바르지 않음',
  account_statement_mismatch: '계정과 재무제표 종류가 다름',
  account_not_valid_for_year: '이 회계연도에 유효하지 않은 계정',
  empty_statement: '금액 행이 없음',
}

export const ruleLabel = (rule: string) => RULE_LABELS[rule] ?? rule

export const UNIT_LABEL: Record<number, string> = { 1: '원', 1000: '천원', 1000000: '백만원' }

/** id 로 노드 찾기 */
export function findNode(nodes: AmountNode[], id: string | null | undefined): AmountNode | null {
  if (!id) return null
  for (const n of nodes) {
    if (n.id === id) return n
    const got = findNode(n.children, id)
    if (got) return got
  }
  return null
}

/** 임시계정을 옮길 수 있는 계정 — 같은 소계 아래 형제(임시계정 제외). 다른 곳이면 소계가 다시 어긋난다(ADR-0037 §2.13) */
export function reclassTargets(nodes: AmountNode[], parentId: string | null | undefined): AmountNode[] {
  return (findNode(nodes, parentId)?.children ?? []).filter((c) => !isSuspenseNode(c))
}

/**
 * 결과 행인가 — 하위를 더하고 **빼서** 나오는 줄(영업이익 = 영업수익 − 영업비용), 또는 그런 줄을 품은 줄
 * (법인세차감전순이익·당기순이익·총포괄이익). 공시 순서 보기에서 구성 항목 **아래**에 놓는다.
 */
export function isResultNode(n: AmountNode): boolean {
  if (!n.children.length) return false
  return n.children.some((c) => c.rollup_sign < 0 || isResultNode(c))
}

export interface StatementRow extends FlatRow {
  /** 결과 행(영업이익·당기순이익 등) — 굵게, 위 구분선 */
  isResult: boolean
}

/**
 * 공시 순서로 편다(K-IFRS 1001 손익계산서 — 매출부터 위에서 아래로). 저장 구조(합계 트리)는 그대로 두고 보기만 바꾼다.
 * - 결과 행: 구성 항목을 **같은 깊이로 먼저** 내놓고 자신은 그 뒤(후위 순회). 접기 없음.
 * - 묶음 행(영업수익·영업비용 등, 더하기만): 머리 → 펼쳤으면 하위 항목을 한 단계 들여서.
 */
export function flattenStatementOrder(nodes: AmountNode[], expanded: Set<string>, depth = 0, out: StatementRow[] = []): StatementRow[] {
  for (const n of nodes) {
    if (isResultNode(n)) {
      flattenStatementOrder(n.children, expanded, depth, out)
      out.push({ node: n, depth, hasChildren: false, expanded: false, isSuspense: isSuspenseNode(n), isResult: true })
      continue
    }
    const hasChildren = n.children.length > 0
    const open = expanded.has(n.id)
    out.push({ node: n, depth, hasChildren, expanded: open, isSuspense: isSuspenseNode(n), isResult: false })
    if (hasChildren && open) flattenStatementOrder(n.children, expanded, depth + 1, out)
  }
  return out
}

/** 공시 순서 보기를 쓰는 재무제표 — 사다리 구조가 있는 손익(포괄손익 포함)·현금흐름 */
export const usesStatementOrder = (statementType: string) => statementType === 'PL' || statementType === 'CF'
