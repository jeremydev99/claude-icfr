import { describe, expect, it } from 'vitest'
import {
  POLICY_GROUPS,
  bytesToMb,
  describeFiscalYear,
  isConflictReasonRequired,
  mbToBytes,
  parseBool,
  parseStartMonth,
  unknownPolicies,
  type PolicyDef,
} from './PolicyDefs.pure'

const def = (key: string) => POLICY_GROUPS.flatMap((g) => g.defs).find((d) => d.key === key) as PolicyDef

describe('parseBool — 서버 해석 규칙과 일치', () => {
  it('not-falsy: 미설정·임의값은 켜짐, false/0/no 만 꺼짐', () => {
    const d = def('dept_approval_enabled')
    if (d.kind !== 'bool') throw new Error()
    expect(parseBool(undefined, d)).toBe(true)
    expect(parseBool('FALSE', d)).toBe(false)
    expect(parseBool('0', d)).toBe(false)
    expect(parseBool('whatever', d)).toBe(true)
  })
  it('truthy: 미설정은 허용(false), true/1/yes 만 금지', () => {
    const d = def('conflict_assessor_control_owner_blocked')
    if (d.kind !== 'bool') throw new Error()
    expect(parseBool(undefined, d)).toBe(false)
    expect(parseBool('Yes', d)).toBe(true)
    expect(parseBool('x', d)).toBe(false)
  })
})

describe('보존기간 검증', () => {
  it('0 은 영구, 5 미만 거부', () => {
    const d = def('evidence_retention_years')
    if (d.kind !== 'number' || !d.validate) throw new Error()
    expect(d.validate('0')).toBeNull()
    expect(d.validate('5')).toBeNull()
    expect(d.validate('3')).not.toBeNull()
    expect(d.validate('5.5')).not.toBeNull()
  })
})

describe('MB 변환', () => {
  it('왕복', () => {
    expect(bytesToMb(String(50 * 1024 * 1024))).toBe('50')
    expect(mbToBytes('50')).toBe(String(50 * 1024 * 1024))
  })
})

describe('회계연도', () => {
  it('시작월 파싱 — 비정상이면 1', () => {
    expect(parseStartMonth(undefined)).toBe(1)
    expect(parseStartMonth('4')).toBe(4)
    expect(parseStartMonth('13')).toBe(1)
    expect(parseStartMonth('abc')).toBe(1)
  })
  it('설명', () => {
    expect(describeFiscalYear(1)).toContain('12월 결산')
    expect(describeFiscalYear(4)).toContain('3월 결산')
  })
})

it('unknownPolicies 는 알려진 키를 제외한다', () => {
  const r = unknownPolicies([
    { policy_key: 'fiscal_year_start_month', policy_value: '1' },
    { policy_key: 'evidence_edit_enabled', policy_value: 'true' },
    { policy_key: 'foo', policy_value: 'bar' },
  ])
  expect(r.map((p) => p.policy_key)).toEqual(['foo'])
})

it('겸직 409 구분 — 사유 요구 vs 정책 금지', () => {
  expect(isConflictReasonRequired('겸직 조합이 발생합니다(assessor=control_owner). 사유를 입력해야 저장할 수 있습니다')).toBe(true)
  expect(isConflictReasonRequired('정책상 금지된 겸직 조합입니다: assessor=control_owner')).toBe(false)
})
