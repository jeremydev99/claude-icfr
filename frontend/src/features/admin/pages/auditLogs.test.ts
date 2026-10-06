import { describe, expect, it } from 'vitest'
import { pageWindow } from './AuditLogsPage'

describe('감사 로그 페이지 번호', () => {
  it('처음·끝과 현재 주변만, 사이는 … (0)', () => {
    expect(pageWindow(1, 1)).toEqual([1])
    expect(pageWindow(1, 5)).toEqual([1, 2, 3, 0, 5])
    expect(pageWindow(10, 20)).toEqual([1, 0, 8, 9, 10, 11, 12, 0, 20])
    expect(pageWindow(20, 20)).toEqual([1, 0, 18, 19, 20])
  })
})
