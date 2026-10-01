/**
 * PWA 설치 상태 판정 (순수 함수) — `pwa.test.ts`.
 *
 * - `prompt`      : 브라우저가 설치 가능 이벤트(beforeinstallprompt)를 줬다 → 설치 버튼
 * - `ios-guide`   : iPhone·iPad Safari — 설치 API 가 없다 → "공유 → 홈 화면에 추가" 안내
 * - `installed`   : 이미 앱 창(standalone)으로 실행 중 → 버튼 숨김
 * - `unsupported` : 그 밖(설치 이벤트가 아직 없거나 지원하지 않는 브라우저) → 버튼 숨김
 */
export type InstallMode = 'prompt' | 'ios-guide' | 'installed' | 'unsupported'

export function isIos(userAgent: string, maxTouchPoints = 0): boolean {
  if (/iPad|iPhone|iPod/.test(userAgent)) return true
  // iPadOS 13+ 는 데스크톱 Safari 로 보고한다 — 터치 지점으로 구분
  return /Macintosh/.test(userAgent) && maxTouchPoints > 1
}

export function installMode(opts: {
  standalone: boolean
  hasPromptEvent: boolean
  userAgent: string
  maxTouchPoints?: number
}): InstallMode {
  if (opts.standalone) return 'installed'
  if (opts.hasPromptEvent) return 'prompt'
  if (isIos(opts.userAgent, opts.maxTouchPoints ?? 0)) return 'ios-guide'
  return 'unsupported'
}
