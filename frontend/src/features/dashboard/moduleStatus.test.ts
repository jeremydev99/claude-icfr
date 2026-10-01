import { describe, expect, it } from 'vitest'
import { effectiveStatus } from './moduleStatus.pure'

describe('effectiveStatus', () => {
  it('데이터가 있으면 실데이터, 없거나 모르면 고정값', () => {
    expect(effectiveStatus('ready', 1897)).toBe('live')
    expect(effectiveStatus('draft', 3)).toBe('live')
    expect(effectiveStatus('api', 2)).toBe('live')
    expect(effectiveStatus('ready', 0)).toBe('ready')
    expect(effectiveStatus('ready', undefined)).toBe('ready')
    expect(effectiveStatus('todo', 5)).toBe('todo')
  })
})
