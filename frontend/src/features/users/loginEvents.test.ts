import { describe, expect, it } from 'vitest'
import { describeDevice, isLocked } from './loginEvents.pure'

describe('describeDevice', () => {
  it('OS·브라우저를 줄여 보여준다', () => {
    expect(describeDevice('Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Version/17.0 Mobile/15E148 Safari/604.1')).toBe('iOS · Safari')
    expect(describeDevice('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36 Edg/124.0')).toBe('Windows · Edge')
    expect(describeDevice('Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 Chrome/124.0 Mobile Safari/537.36')).toBe('Android · Chrome')
    expect(describeDevice('python-requests/2.31')).toBe('기타 · 스크립트')
    expect(describeDevice(null)).toBe('-')
  })
})

describe('isLocked', () => {
  it('잠금 시각이 미래일 때만 잠김', () => {
    const now = new Date('2026-10-01T00:00:00Z')
    expect(isLocked('2026-10-01T00:10:00Z', now)).toBe(true)
    expect(isLocked('2026-09-30T23:59:00Z', now)).toBe(false)
    expect(isLocked(null, now)).toBe(false)
  })
})
