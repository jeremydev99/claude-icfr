import { describe, expect, it } from 'vitest'
import { accountNames, categoryMapComplete, defaultMode, formFields, mappingCounts, uploadSummary } from './upload.pure'
import type { UploadResponse } from './types'

describe('formFields', () => {
  it('빈 값은 보내지 않고, 방식별 필드만', () => {
    expect(formFields('upload', { mode: 'preview' })).toEqual([['mode', 'preview']])
    expect(formFields('upload', {
      mode: 'commit', sheet: 'BS공시', includePrior: true, finalize: false, mapping: { 7: 'new' },
    })).toEqual([['mode', 'commit'], ['sheet', 'BS공시'], ['finalize', 'false'], ['include_prior', 'true'],
      ['mapping', '{"7":"new"}']])
    expect(formFields('attach', {
      mode: 'commit', sheet: 'PL정산표', unit: 1, includePrior: true, categoryMap: { 매출액: '영업수익' }, bridgeColumn: 'J',
    })).toEqual([['mode', 'commit'], ['sheet', 'PL정산표'], ['unit', '1'], ['bridge_column', 'J'],
      ['category_map', '{"매출액":"영업수익"}']])
  })
})

describe('summaries', () => {
  it('정산표는 결합이 기본', () => {
    expect(defaultMode({ sheet: 'BS정산표', kind: 'horizontal_years', statement_type: 'BS' })).toBe('attach')
    expect(defaultMode({ sheet: 'BS공시', kind: 'disclosure_form', statement_type: 'BS' })).toBe('upload')
  })
  it('대응 요약·업로드 요약', () => {
    expect(mappingCounts({ 1: 'a', 2: 'new', 3: 'b' })).toEqual({ existing: 2, created: 1 })
    const r = {
      rows: [
        { row_no: 1, label: '자산', kind: 'section_header', excluded: false, match: null },
        { row_no: 2, label: '현금', kind: 'leaf', excluded: false, match: 'new' },
        { row_no: 3, label: '기본주당이익', kind: 'leaf', excluded: true, match: null },
      ],
      statements: [{ suspense: [{}, {}] }, { suspense: [] }],
      subtotal_diffs: [{}, {}],
    } as unknown as UploadResponse
    expect(uploadSummary(r)).toEqual({ accounts: 1, excluded: ['기본주당이익'], suspense: 2, diffs: 2 })
  })
  it('대응표 후보·완성 여부', () => {
    const t = [{
      id: 'a', name: '영업이익', is_subtotal: true,
      children: [{ id: 'b', name: '영업수익', is_subtotal: false, children: [] }],
    }]
    expect(accountNames(t)).toEqual(['영업이익', '영업수익'])
    expect(categoryMapComplete(['매출액'], {})).toBe(false)
    expect(categoryMapComplete(['매출액'], { 매출액: '영업수익' })).toBe(true)
  })
})
