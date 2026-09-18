// @vitest-environment node
// jsdom 미설치 — 순수 함수만 검증한다(기존 테스트 파일들과 동일 규약).
import { describe, it, expect } from 'vitest'
import { parseStoredTheme } from './sidebarTheme'

describe('parseStoredTheme — 사이드바 테마 저장값', () => {
  it('저장된 값을 그대로 돌려준다', () => {
    expect(parseStoredTheme('light')).toBe('light')
    expect(parseStoredTheme('dark')).toBe('dark')
  })

  it('없거나 알 수 없는 값은 기본값(dark)으로 떨어진다', () => {
    // localStorage 에 옛 값(예: "inverted")이 남아 있어도 화면이 깨지지 않아야 한다.
    expect(parseStoredTheme(null)).toBe('dark')
    expect(parseStoredTheme('')).toBe('dark')
    expect(parseStoredTheme('inverted')).toBe('dark')
  })
})
