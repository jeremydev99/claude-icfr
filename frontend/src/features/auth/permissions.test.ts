// @vitest-environment node
import { describe, it, expect } from 'vitest'
import { isIcfrManagerForUser } from './permissions.pure'
import type { UserProfile } from './store'

const base = {
  id: 'u1', email: 'a@b.c', display_name: '테스트', role: 'user',
  is_active: true, tenants: [], active_tenant_id: null,
} as unknown as UserProfile

describe('isIcfrManagerForUser', () => {
  it('tenant_roles 에 icfr_manager 가 있으면 true', () => {
    expect(isIcfrManagerForUser({ ...base, tenant_roles: ['icfr_manager'], can_write: true })).toBe(true)
  })

  it('can_write 가 true 라도 icfr_manager 가 아니면 false', () => {
    // 두 값을 섞으면 메뉴는 열리는데 서버가 403 을 낸다 — 이 테스트가 그 혼동을 고정한다.
    expect(isIcfrManagerForUser({ ...base, tenant_roles: [], can_write: true })).toBe(false)
    expect(isIcfrManagerForUser({ ...base, tenant_roles: ['auditor'], can_write: true })).toBe(false)
  })

  it('external_auditor 는 false', () => {
    expect(isIcfrManagerForUser({ ...base, tenant_roles: ['external_auditor'], can_write: false })).toBe(false)
  })

  it('로그인 전(null)에도 안전하다', () => {
    expect(isIcfrManagerForUser(null)).toBe(false)
    expect(isIcfrManagerForUser(undefined)).toBe(false)
  })
})
