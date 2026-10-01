import { describe, expect, it } from 'vitest'
import { passwordError, passwordPolicyError } from './password.pure'

describe('passwordError', () => {
  it('순서대로 첫 문제만 알린다', () => {
    expect(passwordError('', 'Abcd1234!x', 'Abcd1234!x')).toContain('현재 비밀번호')
    expect(passwordError('old', 'short', 'short')).toContain('10자')
    expect(passwordError('old', 'Abcd1234!x', 'Abcd1234!y')).toContain('일치하지')
    expect(passwordError('Abcd1234!x', 'Abcd1234!x', 'Abcd1234!x')).toContain('같습니다')
    expect(passwordError('old-pass', 'Abcd1234!x', 'Abcd1234!x')).toBeNull()
  })
})

describe('passwordPolicyError', () => {
  it('10자 이상 + 영문·숫자·특수문자 모두', () => {
    expect(passwordPolicyError('Ab1!')).toContain('10자')
    expect(passwordPolicyError('abcdefghij1')).toContain('특수문자')
    expect(passwordPolicyError('abcdefghij!')).toContain('숫자')
    expect(passwordPolicyError('1234567890!')).toContain('영문')
    expect(passwordPolicyError('한글비밀번호abc1!')).toBeNull()
    expect(passwordPolicyError('correct-horse-9')).toBeNull()
  })
})
