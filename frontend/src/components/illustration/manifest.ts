/**
 * 일러스트 슬롯 목록 — 화면 곳곳의 이미지 자리와, 그 자리를 채울 **생성 프롬프트**를 한 곳에 둔다.
 *
 * 이미지 파일은 `src/assets/illustrations/<slot>.webp` 에 두면 자동으로 쓰인다(Illustration.tsx 의
 * import.meta.glob). 파일이 없으면 브랜드 그라데이션 대체 그래픽이 나온다 — 이미지가 없어도 화면이 깨지지 않는다.
 * 이미지 생성 스크립트(`scripts/gen_illustrations.py`)도 이 파일의 프롬프트를 읽는다 — 프롬프트를 고치면
 * 이 파일만 고친다.
 *
 * 공통 화풍(STYLE)을 모든 프롬프트 앞에 붙여 한 세트로 보이게 한다. 배경은 놓일 자리에 맞춰 슬롯마다 정한다 —
 * 밝은 화면용은 흰 배경(화면에서 multiply 로 카드에 녹인다), 로그인 남색 패널용은 남색 배경.
 */
export const STYLE =
  'Premium enterprise SaaS illustration, soft 3D isometric style, glossy glass and matte surfaces, ' +
  'deep navy (#223052) and muted slate blue-grey (#7385ab) palette with silver-white and pale grey surfaces, ' +
  'tiny warm champagne-gold highlights, NO bright or saturated blue, NO cyan, gentle gradients, ' +
  'subtle soft shadows, calm and trustworthy mood, high detail, ' +
  'no text, no letters, no numbers, no logos, no watermark'

/**
 * 사진 화풍(2026-10-06 마스터 "대문·사이드바·헤드에 이미지를 적극, 과하지 않게") — 히어로·배너 자리에만 쓴다.
 * 빈 상태 일러스트(3D)와 섞이지 않게 사진은 큰 자리에만, 남색·호박색 톤으로 맞춘다.
 */
export const PHOTO_STYLE =
  'Cinematic editorial photograph, shot on full-frame camera with 35mm lens, natural realistic lighting, ' +
  'muted deep navy and slate blue color grading with warm amber accent lights, shallow depth of field, ' +
  'sophisticated corporate atmosphere, Korean business setting, photorealistic, high detail, ' +
  'no text, no readable letters or numbers on screens, no logos, no watermark'

export type IllustrationSlot =
  | 'login-photo'
  | 'sidebar-photo'
  | 'dashboard-photo'
  | 'banner-plan'
  | 'banner-control'
  | 'banner-eval'
  | 'banner-report'
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
  /** 어두운 배경으로 생성 — 밝은 화면용(흰 배경)은 multiply 로 카드에 녹이고, 어두운 것은 그대로 둔다 */
  dark?: boolean
  /** 사진 화풍(PHOTO_STYLE) — 생성 스크립트가 STYLE 대신 붙인다. 화면에서는 object-cover 로 채운다 */
  photo?: boolean
  /** 화면에서의 가로세로비 (생성 크기 선택에도 쓴다) */
  aspect: 'portrait' | 'landscape' | 'square' | 'wide'
  alt: string
  prompt: string
}

export const SLOTS: Record<IllustrationSlot, SlotSpec> = {
  'login-photo': {
    aspect: 'portrait',
    dark: true,
    photo: true,
    alt: '회의실에서 전자칠판의 재무 차트를 함께 보며 감사 회의를 하는 팀',
    prompt:
      'Four Korean business professionals, two men and two women in their 30s to 50s in dark navy and charcoal suits, ' +
      'gathered around a large wall-mounted interactive digital whiteboard in a modern glass-walled meeting room at dusk, ' +
      'the whiteboard shows abstract financial charts, flow diagrams and checklist shapes without any readable text, ' +
      'one woman pointing at the screen while explaining, the others listening and discussing, one man holding a tablet, ' +
      'audit working papers and a laptop on the table, serious collaborative audit meeting mood, ' +
      'city lights softly blurred through the windows, warm pendant lamps, ' +
      'the group and whiteboard on the right two thirds of the frame, the left side darker and calm for overlaid text',
  },
  'sidebar-photo': {
    aspect: 'portrait',
    dark: true,
    photo: true,
    alt: '저녁 무렵 유리 건물과 도시 야경',
    prompt:
      'Looking up at a modern glass office tower at blue hour, geometric facade lines, a few warm lit windows, ' +
      'deep navy sky, calm minimal composition with lots of dark negative space, no people',
  },
  'dashboard-photo': {
    aspect: 'wide',
    photo: true,
    alt: '밝은 회의실에서 보고서를 함께 검토하는 팀',
    prompt:
      'A small Korean finance team of three reviewing printed reports and a laptop together at a light wooden table ' +
      'in a bright modern meeting room with soft daylight, documents and a coffee cup, natural candid moment, ' +
      'people on the right half of the frame, the left half bright, soft and uncluttered for overlaid text',
  },
  'banner-plan': {
    aspect: 'landscape',
    photo: true,
    alt: '계획 — 달력과 노트가 놓인 책상',
    prompt:
      'Top-down view of a tidy desk with a paper wall calendar, a notebook with a pen, a laptop edge and a coffee cup, ' +
      'soft morning light, lots of clean empty space, calm planning mood',
  },
  'banner-control': {
    aspect: 'landscape',
    photo: true,
    alt: '통제 — 정돈된 서류철과 도장',
    prompt:
      'Neatly arranged document binders and folders on a shelf with a company seal stamp and a fountain pen on a desk, ' +
      'soft side light, orderly and secure mood, shallow depth of field',
  },
  'banner-eval': {
    aspect: 'landscape',
    photo: true,
    alt: '평가 — 서류를 검토하는 손과 돋보기',
    prompt:
      'Close-up of hands reviewing printed financial documents with a pen and a magnifying glass on a desk, ' +
      'a laptop blurred in the background, focused auditing mood, soft natural light',
  },
  'banner-report': {
    aspect: 'landscape',
    photo: true,
    alt: '보고 — 이사회 회의실',
    prompt:
      'An empty modern boardroom with a long dark wooden table, leather chairs, a large blank screen on the wall and ' +
      'bound reports placed neatly on the table, evening city view through windows, formal and trustworthy mood',
  },
  'login-hero': {
    aspect: 'portrait',
    dark: true,
    alt: '재무 데이터와 통제 체크리스트가 떠 있는 일러스트',
    prompt:
      'A floating composition of translucent financial dashboard cards, a shield with a checkmark, ' +
      'stacked documents and a bar chart, connected by thin glowing lines, representing internal control over financial reporting, ' +
      'set on a seamless deep navy background (#16203a) with a soft slate-grey glow behind the objects, objects lit with silver rim light',
  },
  'dashboard-hero': {
    aspect: 'wide',
    alt: '진행 현황을 보여주는 대시보드 일러스트',
    prompt:
      'A wide banner scene: a calm workspace of floating analytics panels, a progress ring, a calendar tile and a checklist, ' +
      'arranged left to right with generous empty space on the left half for overlaid text, clean pure white background',
  },
  'empty-default': {
    aspect: 'square',
    alt: '빈 상자 일러스트',
    prompt: 'A single open empty box made of frosted glass with a small sparkle, minimal composition, centered, clean pure white background',
  },
  'empty-search': {
    aspect: 'square',
    alt: '돋보기 일러스트',
    prompt: 'A glass magnifying glass hovering over a blank card, minimal composition, centered, clean pure white background',
  },
  'empty-upload': {
    aspect: 'square',
    alt: '문서 업로드 일러스트',
    prompt: 'A document with an upward arrow rising from a soft cloud tray, minimal composition, centered, clean pure white background',
  },
  'empty-report': {
    aspect: 'square',
    alt: '보고서 일러스트',
    prompt: 'A neat report document with a small pie chart and a signature line, minimal composition, centered, clean pure white background',
  },
  'empty-checklist': {
    aspect: 'square',
    alt: '체크리스트 일러스트',
    prompt: 'A clipboard checklist with three rows and one glowing checkmark, minimal composition, centered, clean pure white background',
  },
  'empty-people': {
    aspect: 'square',
    alt: '팀 일러스트',
    prompt: 'Three abstract rounded person avatars on a soft platform connected by lines, minimal composition, centered, clean pure white background',
  },
  'empty-finance': {
    aspect: 'square',
    alt: '재무제표 일러스트',
    prompt: 'A balance scale made of glass with stacked coins and a ledger sheet, minimal composition, centered, clean pure white background',
  },
}
