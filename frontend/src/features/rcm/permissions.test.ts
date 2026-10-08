// @vitest-environment node
import { describe, it, expect } from 'vitest'
import { canEditHierarchyForUser } from './permissions.pure'
import type { UserProfile } from '../auth/store'

const baseUser: Omit<UserProfile, 'can_write'> = {
  id: 'u-1',
  email: 'user@example.com',
  display_name: 'User',
  role: 'admin',
  tenants: [],
  active_tenant_id: null,
  tenant_roles: [],
}

describe('canEditHierarchyForUser', () => {
  it('can_write=true + 내부회계관리자면 true', () => {
    expect(canEditHierarchyForUser({ ...baseUser, can_write: true, tenant_roles: ['icfr_manager'] })).toBe(true)
  })

  it('can_write=true 라도 관리자가 아니면 false — 바로 반영은 관리자만(2026-10-08)', () => {
    expect(canEditHierarchyForUser({ ...baseUser, can_write: true, tenant_roles: ['icfr_staff'] })).toBe(false)
  })

  it('can_write=false면 false', () => {
    expect(canEditHierarchyForUser({ ...baseUser, can_write: false })).toBe(false)
  })

  it('user=null이면 false', () => {
    expect(canEditHierarchyForUser(null)).toBe(false)
  })
})
