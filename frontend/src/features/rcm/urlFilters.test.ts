// @vitest-environment node
// jsdom 미설치 — 순수 로직만 검증한다(기존 테스트 파일들과 동일 규약).
import { describe, it, expect } from 'vitest'
import { paramsFromUrl } from './urlFilters.pure'
import type { ControlSearchParams } from './types'

const DEFAULTS: ControlSearchParams = { skip: 0, limit: 20, sort_by: 'code', sort_order: 'asc' }

describe('paramsFromUrl — 대시보드 드릴스루', () => {
  it('허용 목록의 필터를 기본값 위에 얹는다', () => {
    const got = paramsFromUrl(new URLSearchParams('assessment_frequency=quarterly'), DEFAULTS)
    expect(got).toEqual({ ...DEFAULTS, assessment_frequency: 'quarterly' })
  })

  it('허용 목록 밖 파라미터는 무시한다', () => {
    // 임의 키가 검색 파라미터로 흘러들면 백엔드가 어떻게 반응하는지 알 수 없다.
    const got = paramsFromUrl(new URLSearchParams('drop_table=1&q=EL'), DEFAULTS)
    expect(got).toEqual({ ...DEFAULTS, q: 'EL' })
  })

  it('is_key_control 은 문자열을 boolean 으로 바꾼다 (백엔드 집계의 "True"/"False" 표기 포함)', () => {
    expect(paramsFromUrl(new URLSearchParams('is_key_control=True'), DEFAULTS).is_key_control).toBe(true)
    expect(paramsFromUrl(new URLSearchParams('is_key_control=false'), DEFAULTS).is_key_control).toBe(false)
  })

  it('알 수 없는 boolean 표기는 필터를 걸지 않는다', () => {
    // "yes" 를 true 로 읽으면 화면은 필터가 걸린 줄 아는데 서버는 다른 판정을 한다.
    expect(paramsFromUrl(new URLSearchParams('is_key_control=yes'), DEFAULTS).is_key_control).toBeUndefined()
  })

  it('빈 값과 없는 값은 기본값을 유지한다', () => {
    expect(paramsFromUrl(new URLSearchParams('q='), DEFAULTS)).toEqual(DEFAULTS)
    expect(paramsFromUrl(new URLSearchParams(''), DEFAULTS)).toEqual(DEFAULTS)
  })

  it('여러 필터를 동시에 받는다', () => {
    const got = paramsFromUrl(new URLSearchParams('process_code=EL&activity=activity_approval'), DEFAULTS)
    expect(got.process_code).toBe('EL')
    expect(got.activity).toBe('activity_approval')
  })
})
