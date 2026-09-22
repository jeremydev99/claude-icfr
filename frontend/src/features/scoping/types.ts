// 스코핑 도메인 타입 (6-1). 백엔드 `schemas/scoping.py` 와 1:1.
//
// **선택지·가이드 범위는 여기 두지 않는다** — `GET /api/scoping/meta` 가 준다(13.9-40).
// 금액은 number(원 단위 정수), 비율은 **문자열**이다 — 비율을 숫자로 주고받으면 부동소수 오차가 생긴다.

export interface Option {
  value: string
  label: string
}

export interface ScopingMeta {
  statement_types: Option[]
  benchmarks: Option[]
  qual_factors: Option[]
  ratings: Option[]
  statuses: Option[]
  origin_statuses: Option[]
  qual_comparisons: Option[]
  benchmark_guide_ranges: Record<string, [string | null, string | null] | null>
  smt_rate_guide_range: [string, string]
  /** 양적 판정을 적용하는 재무제표 종류(BS·PL). 나머지는 "해당 없음" */
  quant_applicable: string[]
}

/** 필드 출처 — `template` 이면 배지("템플릿 문구"), `edited` 면 사용자가 바꿈 */
export type Origin = 'template' | 'edited'

export interface BenchmarkRow {
  kind: string
  label: string
  base_amount: number | null
  effective_base: number | null
  rate: string | null
  amount: number | null
  guide_range: [string | null, string | null] | null
  out_of_range: boolean
  badge: Origin | null
}

export interface Adjustment {
  id: string
  amount: number
  reason: string
}

export interface ScopingTextItem {
  id: string
  key: string
  title: string | null
  body: string
  badge: Origin | null
}

/** 판정 값: Y / N / na(해당 없음 — 주석·현금흐름의 양적) / null(미평가) */
export type Judgement = 'Y' | 'N' | 'na' | null

export interface ScopingAccount {
  id: string
  statement_type: string
  sort_order: number
  group_label: string | null
  name: string
  current_amount: number | null
  prior_amount: number | null
  ratings: Record<string, string>
  qual_basis: string | null
  manual_conclusion: 'Y' | 'N' | null
  manual_reason: string | null
  quant: Judgement
  qual_average: string | null
  qual: Judgement
  computed: Judgement
  final: Judgement
  snapshot_final: Judgement
  /** 필드 단위 배지 { "ratings.q1": "template", "qual_basis": "edited", "manual": ... } */
  badges: Record<string, Origin>
}

export interface HistoryItem {
  id: string
  from_status: string
  to_status: string
  reason: string | null
  badge_count: number | null
  created_at: string
}

export interface ScopingDetail {
  id: string
  fiscal_year: number
  status: 'draft' | 'review' | 'confirmed'
  template_code: string | null
  template_version: number | null
  policy: { threshold: string; comparison: string }
  benchmarks: BenchmarkRow[]
  adjustments: Adjustment[]
  selected_benchmark: string
  overall_materiality: number | null
  smt: number | null
  smt_rate: string | null
  smt_out_of_range: boolean
  rationale: string | null
  scoping_badges: Record<string, Origin>
  texts: ScopingTextItem[]
  accounts: ScopingAccount[]
  warnings: string[]
  badge_count: number
  confirmed_at: string | null
  confirm_reason: string | null
  confirm_badge_count: number | null
  review_auditor: string | null
  review_date: string | null
  review_opinion: string | null
  review_evidence_ref: string | null
  history: HistoryItem[]
  can_edit: boolean
}

export interface ScopingListItem {
  id: string
  fiscal_year: number
  status: string
  template_code: string | null
  template_version: number | null
  confirmed_at: string | null
}

export interface ScopingSummary {
  exists: boolean
  fiscal_year: number | null
  status: string | null
  overall_materiality: number | null
  smt: number | null
  badge_count: number
  by_statement: Record<string, { Y: number; N: number; unevaluated: number }>
}
