import { useEffect, useState } from 'react'
import { cn } from '@/lib/utils'
import type { Judgement, Origin } from '../types'

/** 원 단위 금액 표시. null 은 대시 — 0 과 구분한다 */
export const won = (v: number | null | undefined) => (v === null || v === undefined ? '—' : v.toLocaleString('ko-KR'))

/** 비율 문자열("0.05") → "5%" */
export const pct = (v: string | null | undefined) => {
  if (v === null || v === undefined || v === '') return '—'
  const n = Number(v) * 100
  return `${Number.isInteger(n) ? n : n.toFixed(2).replace(/0+$/, '').replace(/\.$/, '')}%`
}

/**
 * 템플릿 배지 — **필드 단위**다. `template` 이면 "아직 회사가 직접 판단하지 않은 값"이라는 표시.
 * 사용자가 값을 바꿔 저장하면 서버가 `edited` 로 돌리고 배지가 사라진다(같은 값 재저장은 그대로).
 */
export function TemplateBadge({ origin, className }: { origin: Origin | null | undefined; className?: string }) {
  if (origin !== 'template') return null
  return (
    <span
      title="템플릿 문구 — 아직 직접 검토·수정하지 않은 값입니다"
      className={cn('ml-1 inline-block rounded border border-dashed border-sky-300 bg-sky-50 px-1 text-[10px] font-normal text-sky-700', className)}
    >
      템플릿
    </span>
  )
}

/** 판정 표시 — Y / N / 해당 없음 / 미평가 를 **서로 다른 모양**으로 그린다 */
export function JudgementBadge({ value }: { value: Judgement | undefined }) {
  if (value === 'Y') return <span className="rounded bg-red-50 px-1.5 text-xs font-semibold text-red-700">Y</span>
  if (value === 'N') return <span className="rounded bg-muted px-1.5 text-xs text-muted-foreground">N</span>
  if (value === 'na') return <span className="text-xs text-muted-foreground" title="양적 판정 대상이 아닙니다(주석·현금흐름)">해당 없음</span>
  return <span className="rounded border border-dashed px-1 text-xs text-muted-foreground" title="입력이 모자라 판정할 수 없습니다">미평가</span>
}

/**
 * 포커스를 잃을 때만 저장하는 입력칸 — 칸을 옮길 때마다 저장하지 않으면 입력 중 계산이 계속 돈다.
 * `parse` 가 null 을 돌려주면 "비움"으로 저장한다.
 */
export function CommitInput<T>({
  value, format, parse, onCommit, disabled, className, placeholder,
}: {
  value: T
  format: (v: T) => string
  parse: (s: string) => T | undefined
  onCommit: (v: T) => void
  disabled?: boolean
  className?: string
  placeholder?: string
}) {
  const [text, setText] = useState(format(value))
  useEffect(() => setText(format(value)), [value, format])
  return (
    <input
      value={text}
      disabled={disabled}
      placeholder={placeholder}
      onChange={(e) => setText(e.target.value)}
      onBlur={() => {
        const parsed = parse(text)
        if (parsed === undefined) {
          setText(format(value))   // 해석할 수 없는 값 — 되돌린다
          return
        }
        if (format(parsed) !== format(value)) onCommit(parsed)
      }}
      className={cn('h-7 rounded border bg-background px-1.5 text-right text-xs tabular-nums disabled:bg-muted/40', className)}
    />
  )
}

/** "1,234,567" / "-1234" / "" → 정수 또는 null. 해석 불가면 undefined */
export function parseWon(s: string): number | null | undefined {
  const t = s.replace(/[,\s원]/g, '')
  if (t === '') return null
  if (!/^-?\d+$/.test(t)) return undefined
  return Number(t)
}

/** "5" / "5%" / "0.05" → 비율 문자열. 1 보다 크면 백분율로 본다 */
export function parseRate(s: string): string | null | undefined {
  const t = s.replace(/[%\s]/g, '')
  if (t === '') return null
  if (!/^\d+(\.\d+)?$/.test(t)) return undefined
  const n = Number(t)
  return n > 1 ? String(Number((n / 100).toFixed(6))) : t
}
