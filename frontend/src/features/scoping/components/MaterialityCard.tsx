import { useState } from 'react'
import { AlertTriangle, Plus, Trash2 } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import type { Origin, ScopingDetail, ScopingMeta } from '../types'
import { CommitInput, ConfirmToggle, TemplateBadge, parseRate, parseWon, pct, rangeText, won } from './bits'

type Write = (method: 'post' | 'patch' | 'delete', path: string, body?: unknown) => void

const rateFmt = (v: string | null) => (v === null ? '' : pct(v))

/**
 * 중요성 기준 (ADR-0034 §2.3, 6-1b §3.2) — 원천 수식 그대로:
 *   벤치마크 산출액 = ROUND(기준값 × 비율, 0) → 전반중요성 = ROUND(산출액, -3) → 수행중요성 = ROUND(전반 × 설정율, 0)
 * 계산은 전부 서버가 한다. 화면은 입력만 받는다.
 *
 * **비율 가이드 범위·설정율 범위·질적 기준·기준 연도는 전부 회사가 설정한다**(회계연도마다, 감사인 검토 후 확정).
 * 기본값은 템플릿에서 왔고 배지가 붙어 있다. 동의하면 "확인", 다르면 고친다.
 */
export default function MaterialityCard({ d, meta, write }: { d: ScopingDetail; meta: ScopingMeta; write: Write }) {
  const editable = d.can_edit
  const [adjAmount, setAdjAmount] = useState('')
  const [adjReason, setAdjReason] = useState('')
  const [rationale, setRationale] = useState(d.rationale ?? '')
  const origins: Array<Origin | null | undefined> = [
    ...Object.values(d.scoping_badges),
    ...d.benchmarks.flatMap((b) => [b.badge, b.guide_badge]),
  ]
  const bench = (kind: string, body: unknown) => write('patch', `/${d.id}/benchmarks/${kind}`, body)

  return (
    <Card>
      <CardHeader className="flex flex-row flex-wrap items-center justify-between gap-2">
        <CardTitle className="text-base">중요성 기준</CardTitle>
        <ConfirmToggle origins={origins} disabled={!editable} label="중요성 기준 확인"
          onConfirm={(undo) => write('post', `/${d.id}/confirm`, { scope: 'materiality', undo })} />
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="text-xs text-muted-foreground">
              <tr className="border-b">
                <th className="py-1 text-left">선택</th>
                <th className="text-left">벤치마크</th>
                <th className="text-right">기준값(원, FY{d.base_fiscal_year})</th>
                <th className="text-right">비율</th>
                <th className="text-right">산출액</th>
                <th className="pl-3 text-left">비율 가이드 범위 (회사 설정)</th>
              </tr>
            </thead>
            <tbody>
              {d.benchmarks.map((b) => (
                <tr key={b.kind} className="border-b align-top last:border-b-0">
                  <td className="py-1">
                    <input
                      type="radio" name="benchmark" disabled={!editable}
                      checked={d.selected_benchmark === b.kind}
                      onChange={() => write('patch', `/${d.id}`, { selected_benchmark: b.kind })}
                    />
                  </td>
                  <td className="py-1">
                    {b.label}
                    {d.selected_benchmark === b.kind && <TemplateBadge origin={d.scoping_badges.selected_benchmark} />}
                    {b.kind === 'adjusted_pbt' && b.effective_base !== b.base_amount && (
                      <div className="text-[11px] text-muted-foreground">조정 후 {won(b.effective_base)}</div>
                    )}
                  </td>
                  <td className="py-1 text-right">
                    <CommitInput
                      value={b.base_amount} format={(v) => (v === null ? '' : v.toLocaleString('ko-KR'))}
                      parse={parseWon} disabled={!editable} className="w-40"
                      placeholder={b.kind === 'adjusted_pbt' ? '세전이익' : ''}
                      onCommit={(v) => bench(b.kind, { base_amount: v })}
                    />
                  </td>
                  <td className="py-1 text-right">
                    <CommitInput value={b.rate} format={rateFmt} parse={parseRate} disabled={!editable} className="w-20"
                      onCommit={(v) => bench(b.kind, { rate: v })} />
                    <TemplateBadge origin={b.badge} />
                  </td>
                  <td className="py-1 text-right tabular-nums">{won(b.amount)}</td>
                  <td className="py-1 pl-3 text-xs">
                    <div className="flex flex-wrap items-center gap-1">
                      <CommitInput value={b.guide_range?.[0] ?? null} format={rateFmt} parse={parseRate}
                        disabled={!editable} className="w-16" placeholder="하한"
                        onCommit={(v) => bench(b.kind, { guide_low: v })} />
                      <span>~</span>
                      <CommitInput value={b.guide_range?.[1] ?? null} format={rateFmt} parse={parseRate}
                        disabled={!editable} className="w-16" placeholder="상한"
                        onCommit={(v) => bench(b.kind, { guide_high: v })} />
                      <TemplateBadge origin={b.guide_badge} />
                      {b.out_of_range && (
                        <span className="inline-flex items-center gap-0.5 text-amber-700"><AlertTriangle className="h-3 w-3" />범위 밖</span>
                      )}
                    </div>
                    {!b.guide_range && (
                      <div className="text-[11px] text-muted-foreground">
                        범위 없음 — 경고하지 않습니다{b.kind === 'revenue' ? ' (원천 가이드 불분명, 감사인과 합의한 범위를 넣으세요)' : ''}
                      </div>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* 조정세전순이익 — 부호를 붙인 금액을 더한다(감소 조정은 음수) */}
        <div className="rounded-md border p-3">
          <h3 className="mb-2 text-sm font-semibold">조정세전순이익 조정 항목</h3>
          {d.adjustments.length === 0 && <p className="text-xs text-muted-foreground">조정 없음 — 조정세전순이익 = 세전이익</p>}
          <ul className="space-y-1 text-sm">
            {d.adjustments.map((a) => (
              <li key={a.id} className="flex items-center gap-2">
                <span className="w-40 text-right tabular-nums">{won(a.amount)}</span>
                <span className="flex-1">{a.reason}</span>
                {editable && (
                  <Button variant="ghost" size="sm" onClick={() => write('delete', `/${d.id}/adjustments/${a.id}`)}>
                    <Trash2 className="h-3.5 w-3.5" />
                  </Button>
                )}
              </li>
            ))}
          </ul>
          {editable && (
            <div className="mt-2 flex flex-wrap items-center gap-2">
              <input value={adjAmount} onChange={(e) => setAdjAmount(e.target.value)} placeholder="금액(감소는 -)"
                className="h-8 w-40 rounded border px-2 text-right text-sm" />
              <input value={adjReason} onChange={(e) => setAdjReason(e.target.value)} placeholder="사유 (비경상 항목)"
                className="h-8 flex-1 rounded border px-2 text-sm" />
              <Button size="sm" variant="outline" disabled={parseWon(adjAmount) == null || !adjReason.trim()}
                onClick={() => {
                  write('post', `/${d.id}/adjustments`, { amount: parseWon(adjAmount), reason: adjReason })
                  setAdjAmount(''); setAdjReason('')
                }}>
                <Plus className="mr-1 h-3.5 w-3.5" /> 추가
              </Button>
            </div>
          )}
        </div>

        <div className="grid gap-3 sm:grid-cols-3">
          <div className="rounded-md border p-3">
            <p className="text-xs text-muted-foreground">전반중요성 (천원 단위 반올림)</p>
            <p className="text-lg font-semibold tabular-nums">{won(d.overall_materiality)}</p>
          </div>
          <div className="rounded-md border p-3">
            <p className="text-xs text-muted-foreground">
              수행중요성 설정율 <TemplateBadge origin={d.scoping_badges.smt_rate} />
            </p>
            <CommitInput value={d.smt_rate} format={rateFmt} parse={parseRate}
              disabled={!editable} className="mt-1 w-24"
              onCommit={(v) => v !== null && write('patch', `/${d.id}`, { smt_rate: v })} />
            <div className="mt-2 flex flex-wrap items-center gap-1 text-xs text-muted-foreground">
              가이드 범위
              <CommitInput value={d.smt_guide_range?.[0] ?? null} format={rateFmt} parse={parseRate}
                disabled={!editable} className="w-14" placeholder="하한"
                onCommit={(v) => write('patch', `/${d.id}`, { smt_guide_low: v })} />
              ~
              <CommitInput value={d.smt_guide_range?.[1] ?? null} format={rateFmt} parse={parseRate}
                disabled={!editable} className="w-14" placeholder="상한"
                onCommit={(v) => write('patch', `/${d.id}`, { smt_guide_high: v })} />
              <TemplateBadge origin={d.scoping_badges.smt_guide} />
            </div>
            {d.smt_out_of_range && (
              <p className="mt-1 text-xs text-amber-700">가이드 범위({rangeText(d.smt_guide_range)}) 밖</p>
            )}
          </div>
          <div className="rounded-md border p-3">
            <p className="text-xs text-muted-foreground">수행중요성 (유의한 왜곡표시 금액기준)</p>
            <p className="text-lg font-semibold tabular-nums">{won(d.smt)}</p>
          </div>
        </div>

        <div className="grid gap-3 sm:grid-cols-2">
          <div className="rounded-md border p-3 text-sm">
            <p className="text-xs text-muted-foreground">질적 유의 기준 — 10요소 평균(H=3 M=2 L=1)</p>
            <div className="mt-1 flex flex-wrap items-center gap-1">
              평균
              <CommitInput value={d.policy.threshold} format={(v) => v ?? ''}
                parse={(t) => (/^\d+(\.\d+)?$/.test(t.trim()) ? t.trim() : undefined)}
                disabled={!editable} className="w-14"
                onCommit={(v) => write('patch', `/${d.id}`, { qual_threshold: v })} />
              <TemplateBadge origin={d.scoping_badges.qual_threshold} />
              <select value={d.policy.comparison} disabled={!editable}
                onChange={(e) => write('patch', `/${d.id}`, { qual_comparison: e.target.value })}
                className="h-7 rounded border bg-background px-1 text-xs">
                {meta.qual_comparisons.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
              </select>
              <TemplateBadge origin={d.scoping_badges.qual_comparison} />
              이면 유의
            </div>
          </div>
          <div className="rounded-md border p-3 text-sm">
            <p className="text-xs text-muted-foreground">기준 재무제표 연도 — 기준 금액은 직전 연도 결산 확정 금액</p>
            <div className="mt-1 flex items-center gap-1">
              FY
              <CommitInput value={d.base_fiscal_year} format={(v) => String(v)}
                parse={(t) => (/^\d{4}$/.test(t.trim()) ? Number(t.trim()) : undefined)}
                disabled={!editable} className="w-16"
                onCommit={(v) => write('patch', `/${d.id}`, { base_fiscal_year: v })} />
              결산 <span className="text-xs text-muted-foreground">(전년 비교: FY{d.base_fiscal_year - 1})</span>
            </div>
          </div>
        </div>

        <div className="space-y-1">
          <label className="text-sm font-semibold">
            설정근거 <span className="text-xs font-normal text-muted-foreground">— 검토 요청·확정 전 필수</span>
            <TemplateBadge origin={d.scoping_badges.rationale} />
          </label>
          <Textarea value={rationale} disabled={!editable} rows={4} onChange={(e) => setRationale(e.target.value)}
            onBlur={() => rationale !== (d.rationale ?? '') && write('patch', `/${d.id}`, { rationale })} />
        </div>
      </CardContent>
    </Card>
  )
}
