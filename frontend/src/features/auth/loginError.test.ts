import { describe, expect, it } from 'vitest'
import { loginErrorMessage } from './loginError.pure'

describe('loginErrorMessage', () => {
  it('오류 종류별로 다른 안내', () => {
    expect(loginErrorMessage({ response: { status: 401 } })).toContain('비밀번호가 올바르지')
    expect(loginErrorMessage({ response: { status: 403, data: { detail: '비활성 계정' } } })).toBe('비활성 계정')
    expect(loginErrorMessage({ response: { status: 502 } })).toContain('서버 오류')
    expect(loginErrorMessage({ code: 'ECONNABORTED' })).toContain('응답이 없습니다')
    expect(loginErrorMessage({ code: 'ERR_NETWORK' })).toContain('연결할 수 없습니다')
    expect(loginErrorMessage(new Error('x'))).toContain('다시 시도')
  })
})
