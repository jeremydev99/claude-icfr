import { useEffect, useLayoutEffect, useRef, useState } from 'react'
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
 * 출처 배지 — **필드 단위**다(6-1b).
 * - `template` : "템플릿" (점선 하늘색) — 아직 아무도 보지 않은 값. 확정 경고는 이것만 센다
 * - `confirmed`: "확인됨" (실선 초록) — 템플릿 값을 검토하고 동의함
 * - `edited`   : 배지 없음 — 회사가 고친 값
 */
export function TemplateBadge({ origin, className }: { origin: Origin | null | undefined; className?: string }) {
  if (origin === 'template') {
    return (
      <span
        title="템플릿 값 — 아직 아무도 검토하지 않았습니다. 동의하면 '확인', 다르면 고치세요"
        className={cn('ml-1 inline-block rounded border border-dashed border-sky-300 bg-sky-50 px-1 text-[10px] font-normal text-sky-700', className)}
      >
        템플릿
      </span>
    )
  }
  if (origin === 'confirmed') {
    return (
      <span
        title="템플릿 값을 검토하고 동의했습니다"
        className={cn('ml-1 inline-block rounded border border-emerald-300 bg-emerald-50 px-1 text-[10px] font-normal text-emerald-700', className)}
      >
        확인됨
      </span>
    )
  }
  return null
}

/** 칸 테두리 — 배지와 같은 색 구분(선택 상자처럼 배지를 따로 붙이기 어려운 칸용) */
export const originFieldClass = (origin: Origin | null | undefined) =>
  origin === 'template' ? 'border-dashed border-sky-300 bg-sky-50'
    : origin === 'confirmed' ? 'border-emerald-300 bg-emerald-50/60' : ''

/**
 * "확인" / "확인 취소" 버튼 — 범위 안에 템플릿 값이 있으면 확인, 확인한 값만 남았으면 취소.
 * 둘 다 없으면(전부 고친 값) 아무것도 그리지 않는다.
 */
export function ConfirmToggle({ origins, onConfirm, disabled, label = '확인' }: {
  origins: Array<Origin | null | undefined>
  onConfirm: (undo: boolean) => void
  disabled?: boolean
  label?: string
}) {
  const hasTemplate = origins.includes('template')
  const hasConfirmed = origins.includes('confirmed')
  if (disabled || (!hasTemplate && !hasConfirmed)) return null
  return hasTemplate ? (
    <button type="button" onClick={() => onConfirm(false)}
      title="템플릿 값을 검토했고 동의합니다 — 값은 바뀌지 않습니다"
      className="rounded border border-emerald-300 px-1.5 text-[11px] text-emerald-700 hover:bg-emerald-50">
      {label}
    </button>
  ) : (
    <button type="button" onClick={() => onConfirm(true)}
      title="확인을 취소하고 템플릿 상태로 돌립니다"
      className="text-[11px] text-muted-foreground underline">
      확인 취소
    </button>
  )
}

/**
 * 내용에 맞춰 높이가 늘어나는 입력칸 — 판단 근거·수동 판정 사유가 잘리지 않게(6-1b §3.5).
 * 포커스를 잃을 때 저장한다.
 */
export function AutoTextarea({ value, onCommit, disabled, className, placeholder }: {
  value: string
  onCommit: (v: string) => void
  disabled?: boolean
  className?: string
  placeholder?: string
}) {
  const [text, setText] = useState(value)
  const ref = useRef<HTMLTextAreaElement>(null)
  useEffect(() => setText(value), [value])
  useLayoutEffect(() => {
    const el = ref.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${el.scrollHeight}px`
  }, [text])
  return (
    <textarea
      ref={ref} value={text} disabled={disabled} rows={1} placeholder={placeholder}
      onChange={(e) => setText(e.target.value)}
      onBlur={() => text !== value && onCommit(text)}
      className={cn('w-full resize-none overflow-hidden rounded border bg-background px-1.5 py-0.5 text-[11px] leading-snug disabled:bg-muted/40', className)}
    />
  )
}

/** 범위 표시 ["0.05","0.1"] → "5~10%" · [null,"0.03"] → "~3%" · null → 없음 */
export function rangeText(r: [string | null, string | null] | null | undefined): string | null {
  if (!r) return null
  const f = (v: string | null) => (v === null ? '' : pct(v).replace('%', ''))
  return `${f(r[0])}~${f(r[1])}%`
}

/** 증감률 "-0.7500" → "−75.0%" */
export function changeText(v: string | null): string {
  if (v === null) return '—'
  const n = Number(v) * 100
  return `${n > 0 ? '+' : ''}${n.toFixed(1)}%`
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
