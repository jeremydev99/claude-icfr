/** 유의 계정 ↔ RCM 통제 커버리지 (순수 함수·타입) — `coverage.test.ts`. 서버 `ScopingCoverage` 와 같은 모양. */

export interface CoverageControl {
  code: string | null
  name: string | null
  is_key_control: boolean
  match: 'exact' | 'partial'
}

export interface CoverageAccount {
  name: string
  statement_type: string
  controls: CoverageControl[]
  covered: boolean
  key_covered: boolean
}

export interface ScopingCoverage {
  scoping_id: string
  fiscal_year: number
  status: string
  significant_total: number
  covered: number
  uncovered: number
  key_covered: number
  control_total: number
  entity_level_controls: number
  accounts: CoverageAccount[]
  unmatched_rcm_tokens: { token: string; control_codes: string[] }[]
}

/** 통제 있음 비율(%) — 유의 계정이 없으면 0. 소수점 없이 내림(100% 를 과장하지 않는다). */
export function coverageRate(c: Pick<ScopingCoverage, 'significant_total' | 'covered'>): number {
  if (!c.significant_total) return 0
  return Math.floor((c.covered / c.significant_total) * 100)
}

/** 전부 대응이면 ok, 절반 이상이면 warn, 그 밑이면 bad. */
export function coverageTone(c: Pick<ScopingCoverage, 'significant_total' | 'covered'>): 'ok' | 'warn' | 'bad' {
  const r = coverageRate(c)
  if (c.significant_total > 0 && c.covered === c.significant_total) return 'ok'
  return r >= 50 ? 'warn' : 'bad'
}
