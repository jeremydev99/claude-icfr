/**
 * 일러스트 슬롯 목록 — 화면 곳곳의 이미지 자리와, 그 자리를 채울 **생성 프롬프트**를 한 곳에 둔다.
 *
 * 이미지 파일은 `src/assets/illustrations/<slot>.webp` 에 두면 자동으로 쓰인다(Illustration.tsx 의
 * import.meta.glob). 파일이 없으면 브랜드 그라데이션 대체 그래픽이 나온다 — 이미지가 없어도 화면이 깨지지 않는다.
 * 이미지 생성 스크립트(`scripts/gen_illustrations.py`)도 이 파일의 프롬프트를 읽는다 — 프롬프트를 고치면
 * 이 파일만 고친다.
 *
 * 공통 화풍(STYLE)을 모든 프롬프트 앞에 붙여 한 세트로 보이게 한다.
 */
export const STYLE =
  'Premium enterprise SaaS illustration, soft 3D isometric style, glossy glass and matte surfaces, ' +
  'cobalt blue (#1f4fd1) and cyan (#12a4d9) palette with soft lavender accents, gentle gradients, ' +
  'clean white background, subtle soft shadows, calm and trustworthy mood, high detail, ' +
  'no text, no letters, no numbers, no logos, no watermark'

export type IllustrationSlot =
  | 'login-hero'
  | 'dashboard-hero'
  | 'empty-default'
  | 'empty-search'
  | 'empty-upload'
  | 'empty-report'
  | 'empty-checklist'
  | 'empty-people'
  | 'empty-finance'

export interface SlotSpec {
  /** 화면에서의 가로세로비 (생성 크기 선택에도 쓴다) */
  aspect: 'portrait' | 'landscape' | 'square' | 'wide'
  alt: string
  prompt: string
}

export const SLOTS: Record<IllustrationSlot, SlotSpec> = {
  'login-hero': {
    aspect: 'portrait',
    alt: '재무 데이터와 통제 체크리스트가 떠 있는 일러스트',
    prompt:
      'A floating composition of translucent financial dashboard cards, a shield with a checkmark, ' +
      'stacked documents and a bar chart, connected by thin glowing lines, representing internal control over financial reporting',
  },
  'dashboard-hero': {
    aspect: 'wide',
    alt: '진행 현황을 보여주는 대시보드 일러스트',
    prompt:
      'A wide banner scene: a calm workspace of floating analytics panels, a progress ring, a calendar tile and a checklist, ' +
      'arranged left to right with generous empty space on the left half for overlaid text',
  },
  'empty-default': {
    aspect: 'square',
    alt: '빈 상자 일러스트',
    prompt: 'A single open empty box made of frosted glass with a small sparkle, minimal composition, centered',
  },
  'empty-search': {
    aspect: 'square',
    alt: '돋보기 일러스트',
    prompt: 'A glass magnifying glass hovering over a blank card, minimal composition, centered',
  },
  'empty-upload': {
    aspect: 'square',
    alt: '문서 업로드 일러스트',
    prompt: 'A document with an upward arrow rising from a soft cloud tray, minimal composition, centered',
  },
  'empty-report': {
    aspect: 'square',
    alt: '보고서 일러스트',
    prompt: 'A neat report document with a small pie chart and a signature line, minimal composition, centered',
  },
  'empty-checklist': {
    aspect: 'square',
    alt: '체크리스트 일러스트',
    prompt: 'A clipboard checklist with three rows and one glowing checkmark, minimal composition, centered',
  },
  'empty-people': {
    aspect: 'square',
    alt: '팀 일러스트',
    prompt: 'Three abstract rounded person avatars on a soft platform connected by lines, minimal composition, centered',
  },
  'empty-finance': {
    aspect: 'square',
    alt: '재무제표 일러스트',
    prompt: 'A balance scale made of glass with stacked coins and a ledger sheet, minimal composition, centered',
  },
}
