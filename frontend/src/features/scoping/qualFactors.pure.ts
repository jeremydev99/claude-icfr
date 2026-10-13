/** 질적 요소 표시용 — `qualFactors.test.ts`. 요소 이름(전체)은 서버 meta.qual_factors 가 원본이다. */

/** 열 머리글에 쓰는 짧은 이름 — q1~q10 순서. 전체 이름은 툴팁·안내 상자에 */
export const QUAL_SHORT: Record<string, string> = {
  q1: '규모', q2: '추정', q3: '복잡성', q4: '우발', q5: '특수관계',
  q6: '변화', q7: '비경상', q8: '기준변경', q9: '감독', q10: '외부환경',
}

/** 판정 규칙 문장 — 이 스코핑의 질적 기준값·비교 방식으로 만든다 */
export function qualRuleText(policy: { threshold: string; comparison: string }): string {
  const n = Number(policy.threshold)
  const t = Number.isFinite(n) ? String(n) : policy.threshold
  const op = policy.comparison === 'gt' ? '초과' : '이상'
  return `H=3 · M=2 · L=1 점으로 환산해 10개 요소의 평균이 ${t} ${op}이면 질적으로 유의한 계정입니다. 양적(금액) 또는 질적 중 하나라도 유의하면 최종 유의(Y)입니다.`
}

/**
 * 질적 10요소 접힌 표시(2026-10-13) — 요소 순서대로 등급 한 글자, 빈칸은 `·`. 예: `HMML··LLMH`.
 * 표가 가로로 길어 접어 둘 때 한 칸에서 무엇이 비었는지 보이게 한다.
 */
export function ratingsSummary(ratings: Record<string, string | null | undefined>, factors: readonly string[]) {
  const marks = factors.map((f) => ratings[f] || '·')
  const filled = marks.filter((m) => m !== '·').length
  return { text: marks.join(''), filled, total: factors.length }
}
