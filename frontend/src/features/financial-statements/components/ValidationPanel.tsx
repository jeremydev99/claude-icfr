import { CheckCircle2, XCircle } from 'lucide-react'
import { formatAmount, ruleLabel } from '../fsTree.pure'
import type { ValidationResult } from '../types'
import HelpButton from '@/features/help/HelpButton'

/** 검증 결과 (8-D) — 항목을 누르면 그 계정 행으로 이동한다. 확정을 막는 것은 `errors` 뿐이다. */
export default function ValidationPanel({ validation, onSelect }: {
  validation: ValidationResult
  onSelect: (accountId: string) => void
}) {
  const { errors, skipped, checks } = validation
  return (
    <div className="space-y-2 text-xs">
      <div className="flex items-center gap-2">
        {validation.ok
          ? <><CheckCircle2 className="h-4 w-4 text-emerald-600" /><span className="font-medium">검증 통과</span></>
          : <><XCircle className="h-4 w-4 text-red-600" /><span className="font-medium">확정 불가 — 오류 {errors.length}건</span></>}
        <HelpButton k="screen.financial-statements.validation" />
        <span className="text-muted-foreground">
          · 비교 {checks.length}건 · 검사 생략 {skipped.length}건 · 허용 오차 {formatAmount(validation.tolerance)}
        </span>
      </div>
      {errors.length > 0 && (
        <ul className="divide-y rounded border">
          {errors.map((e, i) => (
            <li key={i}>
              <button
                type="button"
                disabled={!e.account_id}
                onClick={() => e.account_id && onSelect(e.account_id)}
                className="flex w-full items-baseline justify-between gap-3 px-3 py-1.5 text-left hover:bg-muted disabled:cursor-default"
              >
                <span>
                  <span className="font-medium text-red-700">{ruleLabel(e.rule)}</span>
                  {e.account_name && <span className="ml-2">{e.account_name}</span>}
                </span>
                {(e.expected !== null || e.actual !== null) && (
                  <span className="tabular-nums text-muted-foreground">
                    기대 {formatAmount(e.expected)} · 실제 {formatAmount(e.actual)}
                    {e.diff !== null && <> · 차액 <b className="text-red-700">{formatAmount(e.diff)}</b></>}
                  </span>
                )}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
