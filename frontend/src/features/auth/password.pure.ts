/**
 * 본인 비밀번호 변경 입력 검사 (순수 함수) — `password.test.ts`.
 * 서버 규칙(`backend/app/core/password_policy.py` — 10자 이상, 영문·숫자·특수문자 모두)과 같게 맞추고,
 * 서버가 모르는 실수(확인 불일치·같은 비밀번호)를 먼저 막는다. 보안 1단계(2026-10-01)에 8자 → 규칙 강화.
 */
export const MIN_PASSWORD_LENGTH = 10
export const PASSWORD_RULE_TEXT = `${MIN_PASSWORD_LENGTH}자 이상, 영문·숫자·특수문자 모두 포함`

/** 비밀번호 규칙 위반 문구 — 사용자 생성·관리자 재설정·본인 변경이 함께 쓴다. */
export function passwordPolicyError(pw: string): string | null {
  if (pw.length < MIN_PASSWORD_LENGTH) return `비밀번호는 ${MIN_PASSWORD_LENGTH}자 이상이어야 합니다`
  const missing = [
    ['영문', /[A-Za-z]/],
    ['숫자', /\d/],
    ['특수문자', /[^A-Za-z0-9\s]/],
  ].filter(([, re]) => !(re as RegExp).test(pw)).map(([name]) => name as string)
  if (missing.length) return `비밀번호에 ${missing.join('·')}를 포함하세요 (영문·숫자·특수문자 모두 필요)`
  return null
}

export function passwordError(current: string, next: string, confirm: string): string | null {
  if (!current) return '현재 비밀번호를 입력하세요'
  const policy = passwordPolicyError(next)
  if (policy) return policy
  if (next !== confirm) return '새 비밀번호 확인이 일치하지 않습니다'
  if (next === current) return '새 비밀번호가 현재 비밀번호와 같습니다'
  return null
}
