import { describe, expect, it } from 'vitest'
import { accessState, addDays, reviewOverdue } from './externalAccess.pure'

describe('externalAccess', () => {
  it('addDays', () => {
    expect(addDays(90, new Date('2026-10-03T10:00:00'))).toBe('2027-01-01')
  })
  it('accessState', () => {
    const u = { status: 'active', valid_from: '2026-10-01', valid_until: '2026-12-31' }
    expect(accessState(u, '2026-10-03').label).toBe('사용 중')
    expect(accessState(u, '2026-12-20').label).toBe('곧 종료')
    expect(accessState(u, '2027-01-01').label).toBe('기간 종료')
    expect(accessState(u, '2026-09-30').label).toBe('시작 전')
    expect(accessState({ ...u, status: 'revoked' }, '2026-10-03').label).toBe('해지')
  })
  it('reviewOverdue', () => {
    const now = new Date('2026-10-03T00:00:00Z')
    expect(reviewOverdue(null, now)).toBe(true)
    expect(reviewOverdue('2026-09-01T00:00:00Z', now)).toBe(false)
    expect(reviewOverdue('2026-06-01T00:00:00Z', now)).toBe(true)
  })
})
