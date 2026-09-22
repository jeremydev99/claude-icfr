import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'
import type { Option } from '../types'

/** 산출 위험 등급. **null 은 "미평가"로 따로 그린다** — Low 와 같은 모양이면 평가해서 낮은 것처럼 읽힌다. */
export function RiskBadge({ grade, options }: { grade: string | null; options: Option[] }) {
  if (grade === null) {
    return <Badge variant="outline" className="border-dashed text-muted-foreground">미평가</Badge>
  }
  const label = options.find((o) => o.value === grade)?.label ?? grade
  return (
    <Badge
      variant="outline"
      className={cn(
        grade === 'high' && 'border-red-200 bg-red-50 text-red-800',
        grade === 'moderate' && 'border-amber-200 bg-amber-50 text-amber-800',
        grade === 'low' && 'border-emerald-200 bg-emerald-50 text-emerald-800',
      )}
    >
      {label}
    </Badge>
  )
}

/** 코드값 → 라벨. 선택지에 없는 값은 코드 그대로(숨기지 않는다). null 은 대시. */
export function labelOf(options: Option[] | undefined, value: string | null): string {
  if (value === null) return '—'
  return options?.find((o) => o.value === value)?.label ?? value
}

/** 서버가 준 에러 문구를 그대로 쓴다 — 409 문구가 무엇을 먼저 해야 하는지 알려준다. */
export const errorDetail = (e: unknown, fallback: string) =>
  (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? fallback
