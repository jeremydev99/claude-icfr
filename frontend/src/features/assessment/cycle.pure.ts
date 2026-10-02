// 평가 회차 생성 순수 로직 — 차수 범위·회차명 제안. React 비의존(node 환경 테스트).
import { KIND_LABEL } from '@/features/schedule/schedule.pure'

export const CYCLE_KINDS = ['operation', 'design'] as const
export const CYCLE_FREQUENCIES = ['annual', 'semiannual', 'quarterly', 'monthly', 'weekly'] as const

/** 회계연도 안의 차수 개수. 주별 53 은 BE 스키마 상한(`period_index le=53`)과 같다. */
export const PERIOD_COUNT: Record<string, number> = {
  annual: 1,
  semiannual: 2,
  quarterly: 4,
  monthly: 12,
  weekly: 53,
}

export function periodIndexOptions(frequency: string): number[] {
  const n = PERIOD_COUNT[frequency] ?? 1
  return Array.from({ length: n }, (_, i) => i + 1)
}

/**
 * 차수 표기. 월별은 차수가 아니라 **기간 시작월**로 적는다 — 회계연도 시작월이 1월이 아니면
 * 1차수 ≠ 1월이라 "1월"이라고 쓰면 틀린다. 시작일을 모르면 차수로 적는다.
 */
export function periodLabel(frequency: string, index: number, periodStart?: string | null): string {
  switch (frequency) {
    case 'annual':
      return '연간'
    case 'semiannual':
      return index === 1 ? '상반기' : '하반기'
    case 'quarterly':
      return `${index}분기`
    case 'monthly': {
      const m = periodStart ? Number(periodStart.slice(5, 7)) : NaN
      return Number.isFinite(m) && m >= 1 ? `${m}월` : `${index}차`
    }
    case 'weekly':
      return `${index}주차`
    default:
      return `${index}차`
  }
}

/** 회차명 제안 — 예: "2026 3분기 운영평가". 담당자가 고칠 수 있다(강제 아님). */
export function suggestCycleName(
  fiscalYear: number,
  kind: string,
  frequency: string,
  index: number,
  periodStart?: string | null,
): string {
  return `${fiscalYear} ${periodLabel(frequency, index, periodStart)} ${KIND_LABEL[kind] ?? kind}`
}

/** 생성 직후 안내. 대상 0건이어도 회차는 만들어진다 — 숨기지 않고 알린다. */
export function createdNotice(targetCount: number | null | undefined): { tone: 'ok' | 'warn'; text: string } {
  if (!targetCount) {
    return { tone: 'warn', text: '회차를 만들었지만 대상 통제가 0건입니다. 이 주기로 평가하는 통제가 없습니다.' }
  }
  return { tone: 'ok', text: `회차를 만들었습니다. 대상 통제 ${targetCount}건이 고정되었습니다.` }
}
