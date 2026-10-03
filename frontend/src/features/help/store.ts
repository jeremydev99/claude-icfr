import { create } from 'zustand'
import { HELP_WIDTH_STORAGE_KEY, clampHelpWidth, parseStoredWidth } from './help.pure'

interface HelpPanelState {
  open: boolean
  /** 스크롤·강조할 키. 패널을 그냥 열면 null. */
  focusKey: string | null
  /** 같은 키를 다시 눌러도 스크롤이 다시 일어나도록 매번 올린다. */
  focusSeq: number
  width: number
  toggle: () => void
  openAt: (key: string) => void
  close: () => void
  setWidth: (width: number) => void
}

function readWidth(): number {
  try {
    return parseStoredWidth(localStorage.getItem(HELP_WIDTH_STORAGE_KEY))
  } catch {
    return parseStoredWidth(null) // 사생활 보호 모드 등 — 기본값
  }
}

/** 매뉴얼 패널 상태. 폭만 이 브라우저(localStorage)에 남긴다 — 개인 설정이다. */
export const useHelpPanel = create<HelpPanelState>((set) => ({
  open: false,
  focusKey: null,
  focusSeq: 0,
  width: readWidth(),
  toggle: () => set((s) => ({ open: !s.open, focusKey: null })),
  openAt: (key) => set((s) => ({ open: true, focusKey: key, focusSeq: s.focusSeq + 1 })),
  close: () => set({ open: false, focusKey: null }),
  setWidth: (width) => {
    const w = clampHelpWidth(width)
    try {
      localStorage.setItem(HELP_WIDTH_STORAGE_KEY, String(w))
    } catch {
      /* 저장 못 하면 이번 창에서만 유지 */
    }
    set({ width: w })
  },
}))
