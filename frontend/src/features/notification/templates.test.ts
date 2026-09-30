// @vitest-environment node
import { describe, it, expect } from 'vitest'
import { renderTemplate, placeholdersOf, TEMPLATES, RULES, SAMPLE_VALUES } from './templates'

describe('renderTemplate', () => {
  it('치환자를 값으로 바꾼다', () => {
    expect(renderTemplate('{{담당자}}님 {{통제코드}} 기한 {{기한}}', { 담당자: '김', 통제코드: 'C-1', 기한: '10/1' }))
      .toBe('김님 C-1 기한 10/1')
  })
  it('공백 허용·반복 치환', () => {
    expect(renderTemplate('{{ 담당자 }}/{{담당자}}', { 담당자: 'A' })).toBe('A/A')
  })
  it('없는 키는 원문 유지', () => {
    expect(renderTemplate('{{담당자}} {{없음}}', { 담당자: 'A' })).toBe('A {{없음}}')
  })
  it('빈 문자열 값도 치환', () => {
    expect(renderTemplate('[{{x}}]', { x: '' })).toBe('[]')
  })
  it('표준 템플릿은 샘플 값으로 전부 치환된다', () => {
    for (const t of TEMPLATES) {
      expect(renderTemplate(t.subject + t.body, SAMPLE_VALUES)).not.toMatch(/\{\{/)
    }
  })
  it('placeholdersOf 는 중복 없이 순서대로', () => {
    expect(placeholdersOf('{{a}} {{b}} {{a}}')).toEqual(['a', 'b'])
  })
  it('규칙은 존재하는 템플릿만 참조', () => {
    const ids = new Set(TEMPLATES.map((t) => t.id))
    for (const r of RULES) expect(ids.has(r.templateId)).toBe(true)
  })
})
