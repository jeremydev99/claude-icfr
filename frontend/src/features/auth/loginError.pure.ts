/**
 * 로그인 실패 문구 (순수 함수) — `loginError.test.ts`.
 *
 * 전에는 어떤 오류든 "이메일 또는 비밀번호가 올바르지 않습니다"였다. LTE(사외망)에서 서버에 **닿지도 못했는데**
 * 비밀번호가 틀린 것처럼 보였다(2026-09-30 모바일 로그인 보고 — 당시 운영 서버는 회사 IP 만 허용).
 * 2026-10-01 사외(443) 허용 후 무응답 문구에서 "사내망 확인" 안내를 뺐다.
 */
export const LOGIN_TIMEOUT_MS = 15_000

interface ErrorLike {
  response?: { status?: number; data?: { detail?: unknown } }
  code?: string
}

export function loginErrorMessage(err: unknown): string {
  const e = (err ?? {}) as ErrorLike
  const status = e.response?.status
  if (status === 401) return '이메일 또는 비밀번호가 올바르지 않습니다'
  if (status === 403) {
    const d = e.response?.data?.detail
    return typeof d === 'string' ? d : '접근 권한이 없습니다'
  }
  if (status === 429) return '로그인 시도가 너무 많습니다 — 잠시 후 다시 시도하세요'
  if (status && status >= 500) return '서버 오류로 로그인하지 못했습니다 — 잠시 후 다시 시도하세요'
  // 응답 자체가 없음: 시간 초과·연결 거부·사외망 차단
  if (!e.response) {
    return e.code === 'ECONNABORTED'
      ? '서버 응답이 없습니다 — 네트워크 연결을 확인하고 잠시 후 다시 시도하세요'
      : '서버에 연결할 수 없습니다 — 네트워크 연결을 확인하고 잠시 후 다시 시도하세요'
  }
  return '로그인하지 못했습니다 — 잠시 후 다시 시도하세요'
}
