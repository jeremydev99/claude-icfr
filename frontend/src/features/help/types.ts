/** `GET /api/help` 응답 한 줄 (ADR-0035). title/body 는 키만 있고 문구가 아직 없을 때 null 이다. */
export interface HelpText {
  key: string
  locale: string
  title: string | null
  body: string | null
  source: string | null
  /** 규정 기준일 `YYYY-MM-DD`. source 가 있을 때만 채워진다. */
  as_of: string | null
  sort_order: number
}
