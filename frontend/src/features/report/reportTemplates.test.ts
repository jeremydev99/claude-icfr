import { describe, expect, it } from 'vitest'
import { computeFacts, type ReportFacts } from './reportModel'
import { DOCS, field, koDate, placeholders, rowsOf, sectionText, type Ctx } from './reportTemplates'

const base = computeFacts({})
const facts = (patch: Partial<ReportFacts> = {}): ReportFacts => ({ ...base, ...patch })
const withTests = (mwOpen: number): ReportFacts => facts({
  tests: { total: 10, done: 10, pass: 9, fail: 1, na: 0, pending: 0 },
  byClass: { ...base.byClass, material_weakness: { total: mwOpen, open: mwOpen } },
})
const ctx = (f: ReportFacts, contents: Ctx['contents'] = {}): Ctx => ({ fy: 2025, facts: f, contents })
const doc = (k: string) => DOCS.find((d) => d.key === k)!
const paraText = (c: Ctx, docKey: string, key: string) => {
  const b = doc(docKey).blocks(c).find((x) => x.kind === 'para' && x.key === key)
  if (!b || b.kind !== 'para') return null
  return sectionText(c, doc(docKey).key, key, b.text).text
}

describe('reportTemplates', () => {
  it('운영실태보고서 결론은 평가 결과로 바뀌고, 중요한 취약점이면 시정 계획 섹션이 생긴다', () => {
    const ok = ctx(withTests(0))
    expect(paraText(ok, 'ops_report', 'conclusion')).toContain('효과적으로 설계되어 운영되고 있다고')
    expect(paraText(ok, 'ops_report', 'mw_plan')).toBeNull()
    const bad = ctx(withTests(2))
    expect(paraText(bad, 'ops_report', 'conclusion')).toContain('중요한 취약점 2건')
    expect(paraText(bad, 'ops_report', 'mw_plan')).toContain('시정 계획')
  })
  it('고친 문단은 그대로, 기본 정보는 자리표시로', () => {
    const c = ctx(withTests(0), { ops_report: { sections: { scope: '직접 쓴 문단' } }, meta: { fields: { company: '주식회사 테스트' } } })
    expect(paraText(c, 'ops_report', 'scope')).toBe('직접 쓴 문단')
    expect(field(c, 'company')).toBe('주식회사 테스트')
    expect(field(c, 'ceo')).toBe('(대표이사)')
  })
  it('감사위원회 평가보고서는 개선 권고가 있으면 시정 의견을 넣는다', () => {
    const none = ctx(withTests(0))
    expect(paraText(none, 'ac_report', 'corrective')).toBeNull()
    const c = ctx(withTests(0), { ac_eval: { rows: { recommendations: [['계획 수립', '연간 계획을 전사 공유']] } } })
    expect(paraText(c, 'ac_report', 'corrective')).toContain('1) 계획 수립: 연간 계획을 전사 공유')
  })
  it('의사록은 위원 명단으로 출석 수와 서명란을 만든다', () => {
    const c = ctx(withTests(0), { meta: { rows: { ac_members: [['위원장', '사외이사', '홍길동'], ['위원', '사외이사', '김철수']] } } })
    expect(paraText(c, 'ac_minutes', 'quorum')).toContain('총수 2명')
    const signers = doc('ac_minutes').blocks(c).find((b) => b.kind === 'signers')
    expect(signers && signers.kind === 'signers' && signers.lines(c).join('\n')).toContain('홍길동')
  })
  it('결산월이 12월이 아니면 기준일·기간이 회계연도 말일로 바뀐다', () => {
    const dec = ctx(withTests(0))
    expect(paraText(dec, 'ops_report', 'scope')).toContain('2025년 12월 31일 현재')
    const mar = { ...ctx(withTests(0)), startMonth: 4 }   // 3월 결산 — 2025 회계연도 = 2025.04.01 ~ 2026.03.31
    expect(paraText(mar, 'ops_report', 'scope')).toContain('2026년 3월 31일 현재')
    expect(paraText(mar, 'ops_report', 'conclusion')).toContain('2026년 3월 31일 현재')
    expect(paraText(mar, 'ac_report', 'scope')).toContain('2026년 3월 31일 현재')
  })
  it('표 기본값과 고친 값, 자리표시 찾기, 날짜', () => {
    const c = ctx(withTests(0))
    expect(rowsOf(c, 'board_ops', 'improvements', [['a']])).toEqual([['a']])
    expect(placeholders('회사 (회사명) 대표 (대표이사) (인)')).toEqual(['회사명', '대표이사'])
    expect(koDate('2026-03-06')).toBe('2026년 03월 06일')
  })
})
