/**
 * 재무제표 (ADR-0037, 8-D) — 백엔드 `schemas/financial_statement.py` 와 1:1.
 *
 * **금액은 문자열 Decimal 이다**("1234.00") — JSON 숫자로 받으면 float 가 된다(백엔드 스키마 주석).
 * 화면 표시는 `fsTree.pure.ts` 의 `formatAmount` 가 문자열 그대로 처리한다(부동소수 변환 없음).
 */

export type Amount = string

export interface Option {
  value: string
  label: string
}

export interface FsMeta {
  statement_types: Option[]
  bases: Option[]
  sections: Option[]
  sections_by_statement: Record<string, string[]>
  units: Option[]
  statuses: Option[]
  source_kinds: Option[]
}

export interface StatementListItem {
  id: string
  fiscal_year: number
  statement_type: string
  basis: string
  unit: number
  currency: string
  tolerance: Amount
  status: 'draft' | 'final'
  finalized_at: string | null
  finalized_by_id: string | null
  source_kind: string | null
  source_filename: string | null
  source_sheet: string | null
}

export interface AmountNode {
  id: string
  code: string | null
  name: string
  statement_type: string
  section: string
  is_subtotal: boolean
  rollup_sign: number
  sort_order: number
  depth: number
  has_row: boolean
  amount: Amount | null
  raw_row_no: number | null
  raw_label: string | null
  raw_indent: number | null
  raw_value: string | null
  raw_meta: Record<string, unknown> | null
  children: AmountNode[]
}

export interface ValidationItem {
  rule: string
  account_id: string | null
  account_code: string | null
  account_name: string | null
  expected: Amount | null
  actual: Amount | null
  diff: Amount | null
}

export interface ValidationResult {
  statement_id: string
  ok: boolean
  unit: number
  currency: string
  tolerance: Amount
  errors: ValidationItem[]
  skipped: ValidationItem[]
  checks: ValidationItem[]
}

export interface StatusEvent {
  id: string
  from_status: string
  to_status: string
  reason: string | null
  actor_id: string
  occurred_at: string
  tolerance: Amount | null
  skipped_count: number | null
  tolerance_diffs: unknown[] | null
}

export interface StatementDetail extends StatementListItem {
  tree: AmountNode[]
  events: StatusEvent[]
  validation: ValidationResult
}

export interface SuspenseResolved {
  action: SuspenseAction
  reason: string
  by: string
  at: string
  amount: string
  target_account_id?: string
}

export interface SuspenseItem {
  amount_id: string
  account_id: string
  parent_account_id: string | null
  parent_name: string | null
  amount: Amount | null
  source_amount: Amount | null
  expected: string | null
  actual: string | null
  resolved: SuspenseResolved | null
  is_deleted: boolean
}

export type SuspenseAction = 'fix_subtotal' | 'reclass' | 'accept'
