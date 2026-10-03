import { describe, expect, it } from 'vitest'
import { allowedPaths, daysLeft, isPathAllowed } from './externalScope.pure'
import type { ExternalInfo, UserProfile } from './store'

const base: UserProfile = {
  id: 'u', email: 'a@b.c', display_name: 'x', role: 'user', tenants: [], active_tenant_id: 't',
  can_write: true, tenant_roles: [],
}
const ext = (e: Partial<ExternalInfo>): UserProfile => ({
  ...base,
  external: { user_type: 'advisor', type_label: '', organization: '', modules: [], valid_from: '2026-01-01',
    valid_until: '2026-12-31', ...e },
})

describe('externalScope', () => {
  it('내부 사용자·PA회계법인·외부감사인은 제한 없음', () => {
    expect(allowedPaths(base)).toBeNull()
    expect(allowedPaths(ext({ user_type: 'advisor' }))).toBeNull()
    expect(allowedPaths(ext({ user_type: 'auditor' }))).toBeNull()
  })
  it('감사위원회는 보고서·현황판·미비점만', () => {
    const u = ext({ user_type: 'committee' })
    expect(isPathAllowed(u, '/report')).toBe(true)
    expect(isPathAllowed(u, '/remediation')).toBe(true)
    expect(isPathAllowed(u, '/scoping')).toBe(false)
  })
  it('세무·기장대리인은 허용 모듈만', () => {
    const u = ext({ user_type: 'specialist', modules: ['financial_statements'] })
    expect(isPathAllowed(u, '/financial-statements')).toBe(true)
    expect(isPathAllowed(u, '/rcm')).toBe(false)
    expect(isPathAllowed(ext({ user_type: 'specialist', modules: [] }), '/financial-statements')).toBe(false)
  })
  it('남은 기간', () => {
    expect(daysLeft(base)).toBeNull()
    expect(daysLeft(ext({ valid_until: '2026-10-10' }), new Date('2026-10-03T09:00:00'))).toBe(7)
    expect(daysLeft(ext({ valid_until: '2026-10-01' }), new Date('2026-10-03T09:00:00'))).toBe(0)
  })
})
