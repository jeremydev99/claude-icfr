import { describe, expect, it } from 'vitest'
import { installMode, isIos } from './pwa.pure'

const CHROME = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/129.0 Safari/537.36'
const IPHONE = 'Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 Version/18.0 Mobile/15E148 Safari/604.1'
const IPAD_DESKTOP = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Version/18.0 Safari/605.1.15'

describe('pwa install mode', () => {
  it('iOS 판정 — iPadOS 는 터치 지점으로', () => {
    expect(isIos(IPHONE)).toBe(true)
    expect(isIos(IPAD_DESKTOP, 5)).toBe(true)
    expect(isIos(IPAD_DESKTOP, 0)).toBe(false)
    expect(isIos(CHROME)).toBe(false)
  })
  it('설치됨 > 설치 이벤트 > iOS 안내 > 미지원', () => {
    expect(installMode({ standalone: true, hasPromptEvent: true, userAgent: CHROME })).toBe('installed')
    expect(installMode({ standalone: false, hasPromptEvent: true, userAgent: CHROME })).toBe('prompt')
    expect(installMode({ standalone: false, hasPromptEvent: false, userAgent: IPHONE })).toBe('ios-guide')
    expect(installMode({ standalone: false, hasPromptEvent: false, userAgent: CHROME })).toBe('unsupported')
  })
})
