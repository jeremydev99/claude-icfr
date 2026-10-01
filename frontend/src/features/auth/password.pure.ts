/**
 * 본인 비밀번호 변경 입력 검사 (순수 함수) — `password.test.ts`.
 * 서버 규칙(새 비밀번호 8자 이상)과 같게 맞추고, 서버가 모르는 실수(확인 불일치·같은 비밀번호)를 먼저 막는다.
 */
export const MIN_PASSWORD_LENGTH = 8

export function passwordError(current: string, next: string, confirm: string): string | null {
  if (!current) return '현재 비밀번호를 입력하세요'
  if (next.length < MIN_PASSWORD_LENGTH) return `새 비밀번호는 ${MIN_PASSWORD_LENGTH}자 이상이어야 합니다`
  if (next !== confirm) return '새 비밀번호 확인이 일치하지 않습니다'
  if (next === current) return '새 비밀번호가 현재 비밀번호와 같습니다'
  return null
}
