/**
 * 매뉴얼 패널 순수 함수 (7-B, ADR-0035).
 *
 * **키를 점으로 쪼개 의미를 뽑지 않는다**(ADR-0035 §2). 여기서는 반대 방향만 한다 —
 * 현재 route 에서 문서화된 규칙(`/` → `.`)으로 조회 **접두사 문자열**을 만든다.
 */

/** 서버 `core/help_keys.KEY_PATTERN` 과 같은 문자 집합. 벗어나면 조회하지 않는다(422 방지). */
const KEY_CHARS = /^[a-z0-9_-]+(\.[a-z0-9_-]+)*$/

/** 경로 속 레코드 id 세그먼트 — UUID 또는 숫자만. 키에서 떼어 낸다. */
const ID_SEGMENT = /^(?:[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}|\d+)$/i

/**
 * route → 키의 route 부분. `/admin/departments` → `admin.departments`.
 * `/`(루트)는 `/dashboard` 로 리다이렉트되므로 `dashboard` 로 본다.
 * id 세그먼트(UUID·숫자)는 뺀다 — `/proposals/<uuid>` → `proposals`.
 * 규칙 밖 문자가 섞이면 null(패널은 용어만 보여준다).
 */
export function routeSegment(pathname: string): string | null {
  const trimmed = pathname.replace(/^\/+|\/+$/g, '')
  if (trimmed === '') return 'dashboard'
  // 상세 화면(`/proposals/:id`)의 id 는 키에 넣지 않는다 — 같은 화면은 같은 도움말을 본다
  const parts = trimmed.split(/\/+/).filter((p) => !ID_SEGMENT.test(p))
  if (parts.length === 0) return null
  const seg = parts.join('.')
  return KEY_CHARS.test(seg) ? seg : null
}

export function menuKeyForRoute(pathname: string): string | null {
  const seg = routeSegment(pathname)
  return seg === null ? null : `menu.${seg}`
}

export function screenPrefixForRoute(pathname: string): string | null {
  const seg = routeSegment(pathname)
  return seg === null ? null : `screen.${seg}`
}

/** 용어 목록 조회 접두사. */
export const TERM_PREFIX = 'term'

// ── 패널 폭 ─────────────────────────────────────────────
export const HELP_WIDTH_MIN = 280
export const HELP_WIDTH_MAX = 640
export const HELP_WIDTH_DEFAULT = 360
export const HELP_WIDTH_STORAGE_KEY = 'icfr.help.width'
/**
 * 이 폭 이상이면 패널이 본문을 **밀고**(입력하면서 읽기), 미만이면 본문 위에 **겹친다**.
 * 1280px = 사이드바 240 + 본문 최소 ~680 + 패널 최대 360(기본). 이보다 좁으면 밀었을 때
 * 본문 표가 너무 좁아져 입력 자체가 어렵다.
 */
export const HELP_PUSH_MIN_VIEWPORT = 1280

/** 폭을 [MIN, MAX] 로 자른다. NaN·비정상 값은 기본값. */
export function clampHelpWidth(width: number): number {
  if (!Number.isFinite(width)) return HELP_WIDTH_DEFAULT
  return Math.round(Math.min(HELP_WIDTH_MAX, Math.max(HELP_WIDTH_MIN, width)))
}

/** localStorage 저장값 → 폭. 없거나 깨졌으면 기본값. */
export function parseStoredWidth(raw: string | null): number {
  if (raw === null || raw.trim() === '') return HELP_WIDTH_DEFAULT
  return clampHelpWidth(Number(raw))
}

// ── 표시 ────────────────────────────────────────────────
/**
 * 규정 인용 표기. source 가 있을 때만 문자열을 만든다 — 기준일 없는 규정 설명은
 * 낡은 판단을 유도하므로(13.9-8) as_of 가 있으면 반드시 함께 붙인다.
 */
export function formatSource(source: string | null | undefined, asOf: string | null | undefined): string | null {
  const s = source?.trim()
  if (!s) return null
  const d = asOf?.trim()
  return d ? `출처: ${s} (기준일 ${d.slice(0, 10)})` : `출처: ${s}`
}

/** 본문이 실제로 작성됐는지. 공백뿐이면 미작성으로 본다. */
export function hasBody(body: string | null | undefined): boolean {
  return Boolean(body && body.trim())
}

export const EMPTY_HELP_MESSAGE = '아직 설명이 작성되지 않았습니다'
