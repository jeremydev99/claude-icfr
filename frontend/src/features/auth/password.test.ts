import { describe, expect, it } from 'vitest'
import { passwordError } from './password.pure'

describe('passwordError', () => {
  it('순서대로 첫 문제만 알린다', () => {
    expect(passwordError('', 'abcd1234', 'abcd1234')).toContain('현재 비밀번호')
    expect(passwordError('old', 'short', 'short')).toContain('8자')
    expect(passwordError('old', 'abcd1234', 'abcd12345')).toContain('일치하지')
    expect(passwordError('abcd1234', 'abcd1234', 'abcd1234')).toContain('같습니다')
    expect(passwordError('old-pass', 'abcd1234', 'abcd1234')).toBeNull()
  })
})
