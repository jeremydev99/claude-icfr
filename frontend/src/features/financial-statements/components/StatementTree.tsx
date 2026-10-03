import EmptyState from '@/components/illustration/EmptyState'
import { ChevronDown, ChevronRight } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'
import { flattenStatementOrder, flattenTree, formatAmount, ruleLabel } from '../fsTree.pure'
import type { AmountNode, ValidationItem } from '../types'

/**
 * 계정 트리 금액표 (8-D). 소계는 굵게, 임시계정(원본 차이)은 노란 바탕, 검증 오류 계정은 빨간 표시.
 * 금액은 **재무제표 단위 그대로**(원으로 환산하지 않는다 — ADR-0037 §2.7).
 * `order="statement"` 는 공시 순서(매출부터 위→아래, 영업이익·당기순이익 같은 결과 행은 구성 항목 아래),
 * `order="tree"` 는 합계 구조(부모 = 자식 합, 최종 합계가 맨 위) — 검증용.
 */
export default function StatementTree({ tree, expanded, onToggle, errors, highlightId, order = 'tree' }: {
  order?: 'tree' | 'statement'
  tree: AmountNode[]
  expanded: Set<string>
  onToggle: (id: string) => void
  errors: Map<string | null, ValidationItem[]>
  highlightId: string | null
}) {
  const rows = order === 'statement'
    ? flattenStatementOrder(tree, expanded)
    : flattenTree(tree, expanded).map((r) => ({ ...r, isResult: false }))
  if (!rows.length) return <EmptyState compact slot="empty-finance" title="금액 행이 없습니다." />
  return (
    <table className="w-full text-xs">
      <thead className="border-b text-muted-foreground">
        <tr>
          <th className="py-2 text-left font-medium">계정</th>
          <th className="w-40 py-2 text-right font-medium">금액</th>
          <th className="w-24 py-2 text-center font-medium">원본 행</th>
          <th className="w-56 py-2 text-left font-medium">검증</th>
        </tr>
      </thead>
      <tbody>
        {rows.map(({ node, depth, hasChildren, expanded: open, isSuspense, isResult }) => {
          const errs = errors.get(node.id) ?? []
          const notes = (node.raw_meta as { notes?: string } | null)?.notes
          return (
            <tr
              key={node.id}
              id={`fs-row-${node.id}`}
              className={cn(
                'border-b last:border-0',
                isResult && 'border-t-2 border-t-foreground/25 bg-muted/40',
                isSuspense && 'bg-amber-50',
                errs.length > 0 && 'bg-red-50/60',
                highlightId === node.id && 'ring-2 ring-inset ring-primary',
              )}
            >
              <td className="py-1.5">
                <div className="flex items-center gap-1" style={{ paddingLeft: depth * 16 }}>
                  {hasChildren ? (
                    <button
                      type="button"
                      className="rounded p-0.5 hover:bg-muted"
                      onClick={() => onToggle(node.id)}
                      aria-label={open ? '접기' : '펼치기'}
                    >
                      {open ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
                    </button>
                  ) : <span className="inline-block w-[18px]" />}
                  <span className={cn(node.is_subtotal && 'font-semibold', isResult && 'font-bold', !node.has_row && 'text-muted-foreground')}
                    title={node.raw_label && node.raw_label !== node.name ? `원본 표기: ${node.raw_label}` : undefined}>
                    {node.name}
                  </span>
                  {isSuspense && <Badge variant="outline" className="border-amber-400 text-amber-700">검토 필요</Badge>}
                  {notes && <span className="text-[10px] text-muted-foreground">주석 {notes}</span>}
                </div>
              </td>
              <td className={cn('py-1.5 text-right tabular-nums', node.is_subtotal && 'font-semibold', isResult && 'font-bold')}>
                {node.has_row ? formatAmount(node.amount) : ''}
              </td>
              <td className="py-1.5 text-center text-muted-foreground">{node.raw_row_no ?? ''}</td>
              <td className="py-1.5">
                {errs.map((e, i) => (
                  <span key={i} className="block text-red-700">
                    {ruleLabel(e.rule)}{e.diff ? ` · 차액 ${formatAmount(e.diff)}` : ''}
                  </span>
                ))}
              </td>
            </tr>
          )
        })}
      </tbody>
    </table>
  )
}
