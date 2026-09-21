// @vitest-environment node
// jsdom 미설치 — 순수 함수만 검증한다(기존 테스트 파일들과 동일 규약).
import { describe, it, expect } from 'vitest'
import { parseStoredTheme } from './sidebarTheme'

describe('parseStoredTheme — 사이드바 테마 저장값', () => {
  it('저장된 값을 그대로 돌려준다', () => {
    expect(parseStoredTheme('gray')).toBe('gray')
    expect(parseStoredTheme('white')).toBe('white')
    expect(parseStoredTheme('navy')).toBe('navy')
  })

  it('구 이름(dark/light)은 버리지 않고 옮긴다', () => {
    // 이미 저장한 브라우저가 있다. 이름을 바꿨다고 설정이 초기화되면 안 된다.
    // 구 'dark' 는 실제로 밝은 회색이었으므로 gray 다.
    expect(parseStoredTheme('dark')).toBe('gray')
    expect(parseStoredTheme('light')).toBe('white')
  })

  it('없거나 알 수 없는 값은 기본값(gray)으로 떨어진다', () => {
    expect(parseStoredTheme(null)).toBe('gray')
    expect(parseStoredTheme('')).toBe('gray')
    expect(parseStoredTheme('inverted')).toBe('gray')
  })
})
