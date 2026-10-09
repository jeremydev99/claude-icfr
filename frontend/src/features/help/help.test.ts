import { describe, expect, it } from 'vitest'
import {
  HELP_WIDTH_DEFAULT,
  HELP_WIDTH_MAX,
  HELP_WIDTH_MIN,
  clampHelpWidth,
  formatSource,
  hasBody,
  menuKeyForRoute,
  parseStoredWidth,
  routeSegment,
  screenPrefixForRoute,
} from './help.pure'

describe('route → 키 접두사', () => {
  it('단일 route', () => {
    expect(menuKeyForRoute('/scoping')).toBe('menu.scoping')
    expect(screenPrefixForRoute('/scoping')).toBe('screen.scoping')
  })
  it('중첩 route 의 / 는 . 으로', () => {
    expect(menuKeyForRoute('/admin/departments')).toBe('menu.admin.departments')
    expect(screenPrefixForRoute('/admin/departments/')).toBe('screen.admin.departments')
  })
  it('루트는 dashboard', () => {
    expect(routeSegment('/')).toBe('dashboard')
    expect(routeSegment('')).toBe('dashboard')
    expect(menuKeyForRoute('/dashboard')).toBe('menu.dashboard')
  })
  it('상세 화면의 id 세그먼트는 뗀다', () => {
    expect(routeSegment('/proposals/3f2b8c1e-9a4d-4e6f-8b2a-1c3d5e7f9a0b')).toBe('proposals')
    expect(menuKeyForRoute('/proposals/3F2B8C1E-9A4D-4E6F-8B2A-1C3D5E7F9A0B/')).toBe('menu.proposals')
    expect(screenPrefixForRoute('/proposals/42')).toBe('screen.proposals')
    expect(routeSegment('/rcm/links')).toBe('rcm.links')
  })
  it('키 문자 집합 밖이면 null', () => {
    expect(routeSegment('/Users')).toBeNull()
    expect(menuKeyForRoute('/rcm/한글')).toBeNull()
    expect(screenPrefixForRoute('/a b')).toBeNull()
  })
})

describe('패널 폭', () => {
  it('범위로 자른다', () => {
    expect(clampHelpWidth(100)).toBe(HELP_WIDTH_MIN)
    expect(clampHelpWidth(5000)).toBe(HELP_WIDTH_MAX)
    expect(clampHelpWidth(400.4)).toBe(400)
  })
  it('비정상 값은 기본값', () => {
    expect(clampHelpWidth(Number.NaN)).toBe(HELP_WIDTH_DEFAULT)
    expect(parseStoredWidth(null)).toBe(HELP_WIDTH_DEFAULT)
    expect(parseStoredWidth('abc')).toBe(HELP_WIDTH_DEFAULT)
    expect(parseStoredWidth('')).toBe(HELP_WIDTH_DEFAULT)
    expect(parseStoredWidth('9999')).toBe(HELP_WIDTH_MAX)
    expect(parseStoredWidth('420')).toBe(420)
  })
})

describe('출처 표기', () => {
  it('출처 + 기준일', () => {
    expect(formatSource('외부감사법 제8조', '2024-01-01')).toBe('출처: 외부감사법 제8조 (기준일 2024-01-01)')
  })
  it('기준일이 datetime 문자열이어도 날짜만', () => {
    expect(formatSource('규정', '2024-01-01T00:00:00')).toBe('출처: 규정 (기준일 2024-01-01)')
  })
  it('출처가 없으면 null', () => {
    expect(formatSource(null, '2024-01-01')).toBeNull()
    expect(formatSource('  ', null)).toBeNull()
  })
  it('기준일 없이 출처만', () => {
    expect(formatSource('규정', null)).toBe('출처: 규정')
  })
})

describe('본문 작성 여부', () => {
  it('null·공백은 미작성', () => {
    expect(hasBody(null)).toBe(false)
    expect(hasBody('  \n')).toBe(false)
    expect(hasBody('내용')).toBe(true)
  })
})
