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

// ── 8-D2 업로드 (백엔드 UploadResponse·AttachResponse) ─────────────

export interface UploadSheetCandidate {
  sheet: string
  kind: 'disclosure_form' | 'horizontal_years'
  statement_type: string | null
}

export interface UploadStatementResult {
  fiscal_year: number
  statement_id: string | null
  status: string
  finalize_candidate: boolean
  finalized: boolean
  ok: boolean
  errors: { rule: string; raw_row_no: number | null; account_name: string | null; diff: Amount | null }[]
  skipped: unknown[]
  checks_count: number
  suspense: { parent_account_id: string; parent_name: string; amount: Amount }[]
}

export interface UploadConflict {
  fiscal_year: number
  statement_id: string
  status: string
}

export interface UploadRow {
  row_no: number
  label: string
  kind: string
  excluded: boolean
  match: string | null
}

export interface UploadResponse {
  mode: string
  committed: boolean
  can_commit: boolean
  sheet: string | null
  kind: string | null
  statement_type: string | null
  basis: string | null
  unit: number | null
  unit_label: string | null
  periods: number[]
  fiscal_years: number[]
  sheets: UploadSheetCandidate[]
  errors: string[]
  warnings: string[]
  master_empty: boolean
  mapping_required: boolean
  suggested_mapping: Record<string, string>
  conflicts: UploadConflict[]
  rows: UploadRow[]
  subtotal_diffs: { row_no: number; label: string; fiscal_year: number; diff: Amount }[]
  statements: UploadStatementResult[]
}

export interface AttachRowOut {
  row_no: number
  name: string
  target_name: string | null
  existing_account_id: string | null
  skip_reason: string | null
}

export interface AttachResponse {
  mode: string
  committed: boolean
  can_commit: boolean
  sheet: string | null
  statement_type: string | null
  basis: string | null
  unit: number | null
  bridge_column: string | null
  bridge_candidates: { column: string; values: number; matched: number }[]
  periods: number[]
  fiscal_years: number[]
  errors: string[]
  warnings: string[]
  conflicts: UploadConflict[]
  unmatched: string[]
  rows: AttachRowOut[]
  statements: UploadStatementResult[]
}

export interface AccountNode {
  id: string
  name: string
  is_subtotal: boolean
  children: AccountNode[]
}
