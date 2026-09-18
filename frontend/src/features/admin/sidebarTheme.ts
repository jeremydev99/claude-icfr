import { create } from 'zustand'

/**
 * 사이드바 테마 — **개인 설정**이며 localStorage 에만 산다(B-1).
 *
 * 회사 전체 설정으로 두지 않은 이유: 색 취향은 사람마다 다르고 관리자가 강제할 이유가 없다.
 * 개인 설정이면 백엔드 작업이 0 이다 — 회사 설정이면 `tenant_policies` 와 API 가 필요하다.
 *
 * **이름을 색으로 바꿨다(gray/white/navy).** 앞서 dark/light 로 뒀는데 기본값이 실제로는
 * 밝은 회색이라 그 축에 애매하게 걸렸다 — "다크인데 밝다"는 설명이 필요해지는 이름은
 * 이름이 틀린 것이다. 색 이름은 화면을 보면 바로 맞출 수 있고, 나중에 본문까지 테마를
 * 넓혀 진짜 어두운 팔레트가 생겨도 `navy` 는 여전히 남색이라 이름이 흔들리지 않는다.
 */
export type SidebarTheme = 'gray' | 'white' | 'navy'

export const SIDEBAR_THEME_STORAGE_KEY = 'icfr.sidebarTheme'
const DEFAULT_THEME: SidebarTheme = 'gray'

/** 선택 UI 순서·표기. 값이 늘면 여기만 고치면 된다. */
export const SIDEBAR_THEMES: Array<{ value: SidebarTheme; label: string }> = [
  { value: 'gray', label: '회색' },
  { value: 'white', label: '흰색' },
  { value: 'navy', label: '남색' },
]

/** 구 이름 → 새 이름. **이미 저장된 브라우저가 있으므로 버리지 않고 옮긴다.** */
const LEGACY_THEMES: Record<string, SidebarTheme> = {
  dark: 'gray',   // 구 'dark' 는 실제로 밝은 회색이었다
  light: 'white',
}

/** 저장값 → 테마. 구 이름은 옮기고, 알 수 없는 값은 기본값으로 떨어뜨린다(순수 함수). */
export function parseStoredTheme(raw: string | null): SidebarTheme {
  if (raw === 'gray' || raw === 'white' || raw === 'navy') return raw
  return (raw && LEGACY_THEMES[raw]) || DEFAULT_THEME
}

function readStoredTheme(): SidebarTheme {
  try {
    return parseStoredTheme(localStorage.getItem(SIDEBAR_THEME_STORAGE_KEY))
  } catch {
    // 사파리 프라이빗 모드 등에서 localStorage 접근 자체가 던진다 — 화면은 떠야 한다.
    return DEFAULT_THEME
  }
}

/** CSS 변수 전환 지점. `index.css` 가 `:root[data-sidebar-theme='navy']` 로 값을 덮는다. */
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
