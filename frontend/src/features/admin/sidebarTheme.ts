import { create } from 'zustand'

/**
 * 사이드바 테마 — **개인 설정**이며 localStorage 에만 산다(B-1).
 *
 * 회사 전체 설정으로 두지 않은 이유: 색 취향은 사람마다 다르고 관리자가 강제할 이유가 없다.
 * 개인 설정이면 백엔드 작업이 0 이다 — 회사 설정이면 `tenant_policies` 와 API 가 필요하다.
 *
 * 이름을 "음영 반전"이 아니라 dark/light 로 둔 이유: 나중에 본문 영역까지 테마를 넓힐 때
 * 이름이 그대로 쓰인다. "음영 반전"은 그때 의미를 잃는다.
 *
 * **현재 `dark` 는 "본문보다 어두운 회색 사이드바"다**(`--sidebar: 220 14% 92%`, 오늘 화면).
 * 진짜 어두운 팔레트는 본문까지 테마를 넓히는 시점에 이 이름 아래로 들어온다.
 */
export type SidebarTheme = 'dark' | 'light'

export const SIDEBAR_THEME_STORAGE_KEY = 'icfr.sidebarTheme'
const DEFAULT_THEME: SidebarTheme = 'dark'

/** 저장값 → 테마. 알 수 없는 값·빈 값은 기본값으로 떨어뜨린다(순수 함수라 테스트 대상). */
export function parseStoredTheme(raw: string | null): SidebarTheme {
  return raw === 'light' || raw === 'dark' ? raw : DEFAULT_THEME
}

function readStoredTheme(): SidebarTheme {
  try {
    return parseStoredTheme(localStorage.getItem(SIDEBAR_THEME_STORAGE_KEY))
  } catch {
    // 사파리 프라이빗 모드 등에서 localStorage 접근 자체가 던진다 — 화면은 떠야 한다.
    return DEFAULT_THEME
  }
}

/** CSS 변수 전환 지점. `index.css` 가 `:root[data-sidebar-theme='light']` 로 값을 덮는다. */
export function applySidebarTheme(theme: SidebarTheme): void {
  document.documentElement.dataset.sidebarTheme = theme
}

interface SidebarThemeState {
  theme: SidebarTheme
  setTheme: (theme: SidebarTheme) => void
}

export const useSidebarTheme = create<SidebarThemeState>((set) => ({
  theme: readStoredTheme(),
  setTheme: (theme) => {
    try {
      localStorage.setItem(SIDEBAR_THEME_STORAGE_KEY, theme)
    } catch {
      // 저장이 안 돼도 이번 세션의 전환은 되게 둔다.
    }
    applySidebarTheme(theme)
    set({ theme })
  },
}))
