/** 로그인 기록·잠금 표시 (순수 함수) — `loginEvents.test.ts`. 보안 1단계(2026-10-01). */

export const LOGIN_REASON_LABEL: Record<string, string> = {
  ok: '성공',
  bad_password: '비밀번호 오류',
  unknown_email: '없는 계정',
  locked: '잠김 상태 시도',
  inactive: '비활성 계정',
}

/** User-Agent 를 "iPhone · Safari" 정도로 줄인다. 정확한 판별이 목적이 아니라 낯선 기기를 알아보는 용도다. */
export function describeDevice(ua: string | null | undefined): string {
  if (!ua) return '-'
  const os = /iPhone|iPad/.test(ua) ? 'iOS' : /Android/.test(ua) ? 'Android' : /Windows/.test(ua) ? 'Windows'
    : /Mac OS X/.test(ua) ? 'macOS' : /Linux/.test(ua) ? 'Linux' : '기타'
  const browser = /Edg\//.test(ua) ? 'Edge' : /SamsungBrowser/.test(ua) ? 'Samsung' : /KAKAOTALK/i.test(ua) ? 'KakaoTalk'
    : /Chrome\//.test(ua) ? 'Chrome' : /Firefox\//.test(ua) ? 'Firefox' : /Safari\//.test(ua) ? 'Safari'
    : /curl|python|Go-http/i.test(ua) ? '스크립트' : '기타'
  return `${os} · ${browser}`
}

/** 지금 잠겨 있는가 — 잠금 시각이 지나면 서버도 다음 로그인에서 풀어 준다. */
export function isLocked(lockedUntil: string | null | undefined, now: Date = new Date()): boolean {
  return !!lockedUntil && new Date(lockedUntil).getTime() > now.getTime()
}
