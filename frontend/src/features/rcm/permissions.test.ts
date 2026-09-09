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
  it('can_write=true면 true', () => {
    expect(canEditHierarchyForUser({ ...baseUser, can_write: true })).toBe(true)
  })

  it('can_write=false면 false', () => {
    expect(canEditHierarchyForUser({ ...baseUser, can_write: false })).toBe(false)
  })

  it('user=null이면 false', () => {
    expect(canEditHierarchyForUser(null)).toBe(false)
  })
})
