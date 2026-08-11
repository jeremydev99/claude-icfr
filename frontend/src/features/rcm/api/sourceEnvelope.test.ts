// @vitest-environment node
import { describe, it, expect, vi, afterEach } from 'vitest'
import {
  buildSourceEnvelope,
  buildOptionalSourceEnvelope,
  isBaseline,
  isTenantAdd,
  resolveDeleteSemantics,
} from './sourceEnvelope'

afterEach(() => {
  vi.unstubAllEnvs()
})

describe('buildSourceEnvelope', () => {
  it('flat 필드가 모두 존재하면 nested envelope로 정상 조립한다', () => {
    const dto = { id: 'ctrl-1', source: 'tenant' as const, baseline_id: null, is_overridden: false }
    expect(buildSourceEnvelope(dto)).toEqual({
      id: 'ctrl-1',
      source: 'tenant',
      baseline_id: null,
      is_overridden: false,
    })
  })

  it('id는 신규 wrapper 필드가 아니라 기존 item identity 필드를 그대로 재사용한다', () => {
    const dto = { id: 'ctrl-existing-id', source: 'baseline' as const, baseline_id: 'base-1', is_overridden: true }
    expect(buildSourceEnvelope(dto).id).toBe('ctrl-existing-id')
  })

  it('DEV 모드에서 필수 필드(source/baseline_id/is_overridden) 누락 시 명시적으로 throw한다', () => {
    vi.stubEnv('DEV', true)
    const dto = { id: 'ctrl-2', source: undefined, baseline_id: null, is_overridden: false } as any
    expect(() => buildSourceEnvelope(dto)).toThrow(/계약 위반/)
  })

  it('프로덕션 모드에서 필드 누락 시 throw하지 않고 안전한 최소값으로 폴백한다', () => {
    vi.stubEnv('DEV', false)
    const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
    const dto = { id: 'ctrl-3', source: undefined, baseline_id: null, is_overridden: false } as any
    expect(buildSourceEnvelope(dto)).toEqual({
      id: 'ctrl-3',
      source: 'tenant',
      baseline_id: null,
      is_overridden: false,
    })
    expect(consoleErrorSpy).toHaveBeenCalledTimes(1)
    consoleErrorSpy.mockRestore()
  })
})

describe('buildOptionalSourceEnvelope', () => {
  it('flat 필드가 모두 존재하면 nested envelope로 조립한다', () => {
    const dto = { id: 'proc-1', source: 'baseline' as const, baseline_id: 'base-9', is_overridden: true }
    expect(buildOptionalSourceEnvelope(dto)).toEqual({
      id: 'proc-1',
      source: 'baseline',
      baseline_id: 'base-9',
      is_overridden: true,
    })
  })

  it('source가 없으면(레거시 응답) undefined를 반환하고 크래시하지 않는다', () => {
    const dto = { id: 'proc-2' }
    expect(buildOptionalSourceEnvelope(dto)).toBeUndefined()
  })

  it('source는 있으나 baseline_id/is_overridden이 없으면 안전 기본값(null/false)으로 채운다', () => {
    const dto = { id: 'proc-3', source: 'tenant' as const }
    expect(buildOptionalSourceEnvelope(dto)).toEqual({
      id: 'proc-3',
      source: 'tenant',
      baseline_id: null,
      is_overridden: false,
    })
  })
})

describe('isBaseline', () => {
  it('baseline 아이템이면 true', () => {
    expect(isBaseline({ id: '1', source: 'baseline', baseline_id: null, is_overridden: false })).toBe(true)
  })

  it('tenant-added 아이템이면 false', () => {
    expect(isBaseline({ id: '2', source: 'tenant', baseline_id: null, is_overridden: false })).toBe(false)
  })

  it('envelope 없음(레거시)이면 false로 폴백한다', () => {
    expect(isBaseline(undefined)).toBe(false)
  })
})

describe('isTenantAdd', () => {
  it('tenant-added 아이템이면 true', () => {
    expect(isTenantAdd({ id: '1', source: 'tenant', baseline_id: null, is_overridden: false })).toBe(true)
  })

  it('baseline 아이템이면 false', () => {
    expect(isTenantAdd({ id: '2', source: 'baseline', baseline_id: null, is_overridden: false })).toBe(false)
  })

  it('envelope 없음(레거시)이면 false로 폴백한다', () => {
    expect(isTenantAdd(undefined)).toBe(false)
  })
})

describe('resolveDeleteSemantics', () => {
  it('baseline 유래 아이템은 exclude', () => {
    expect(
      resolveDeleteSemantics({ id: '1', source: 'baseline', baseline_id: null, is_overridden: false }),
    ).toBe('exclude')
  })

  it('tenant 추가분은 soft_delete', () => {
    expect(
      resolveDeleteSemantics({ id: '2', source: 'tenant', baseline_id: null, is_overridden: false }),
    ).toBe('soft_delete')
  })

  it('is_overridden 값과 무관하게 baseline 유래면 exclude를 유지한다 (source만 판정에 사용)', () => {
    expect(
      resolveDeleteSemantics({ id: '3', source: 'baseline', baseline_id: 'base-1', is_overridden: true }),
    ).toBe('exclude')
  })

  it('envelope 없음(미전환 API)이면 기존 동작인 soft_delete로 폴백한다', () => {
    expect(resolveDeleteSemantics(undefined)).toBe('soft_delete')
  })
})
