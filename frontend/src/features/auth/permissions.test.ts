// @vitest-environment node
import { describe, it, expect } from 'vitest'
import { canViewAllForUser, isIcfrManagerForUser, isNavHidden } from './permissions.pure'
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

describe('canViewAllForUser — 증빙 관리·전체 보기(조사 4)', () => {
  const as = (roles: string[]) => ({ ...base, tenant_roles: roles, can_write: true })
  it.each([
    [['icfr_staff'], true], [['icfr_lead'], true], [['icfr_manager'], true],
    [['auditor'], true], [['external_auditor'], true], [['external_advisor'], true],
    [[], false], [['sys_admin'], false],
  ])('%j → %s', (roles, expected) => {
    expect(canViewAllForUser(as(roles))).toBe(expected)
  })
  it('로그인 전(null)에도 안전하다', () => {
    expect(canViewAllForUser(null)).toBe(false)
  })
})

describe('isNavHidden — 증빙 관리 메뉴는 권한 없으면 아예 감춘다', () => {
  const as = (roles: string[]) => ({ ...base, tenant_roles: roles, can_write: true })
  it('requiresFullViewer 메뉴만 대상', () => {
    expect(isNavHidden({ requiresFullViewer: true }, as([]))).toBe(true)
    expect(isNavHidden({ requiresFullViewer: true }, as(['sys_admin']))).toBe(true)
    expect(isNavHidden({ requiresFullViewer: true }, as(['icfr_staff']))).toBe(false)
    expect(isNavHidden({}, as([]))).toBe(false)
  })
  it('관리자 메뉴(역할 배정·정책·감사 로그)는 마스터관리자 아니면 감춘다 — 자물쇠 아님', () => {
    expect(isNavHidden({ requiresIcfrManager: true }, as(['icfr_lead']))).toBe(true)
    expect(isNavHidden({ requiresIcfrManager: true }, as(['icfr_manager']))).toBe(false)
  })
  it('관리자 영역(부서·회계연도·계정·메일)은 일반 사용자에게 감춘다', () => {
    expect(isNavHidden({ adminArea: true }, as([]))).toBe(true)
    expect(isNavHidden({ adminArea: true }, as(['icfr_staff']))).toBe(false)
    expect(isNavHidden({ adminArea: true }, as(['sys_admin']))).toBe(false)
    expect(isNavHidden({ adminArea: true }, { ...as([]), role: 'admin' })).toBe(false)
  })
})
