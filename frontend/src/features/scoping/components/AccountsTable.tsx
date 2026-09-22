import { useMemo, useState } from 'react'
import { cn } from '@/lib/utils'
import type { ScopingAccount, ScopingDetail, ScopingMeta } from '../types'
import { CommitInput, JudgementBadge, TemplateBadge, parseWon } from './bits'

type Write = (method: 'post' | 'patch' | 'delete', path: string, body?: unknown) => void

/**
 * 계정 평가 (ADR-0034 §2.4) — 재무제표 종류별 탭.
 *
 * - 양적: |당기 금액| ≥ 수행중요성. **주석·현금흐름은 "해당 없음"**(원천 각주) — 금액칸도 두지 않는다
 * - 질적: 10요소 H/M/L 평균이 기준값 이상. **하나라도 비면 미평가**(0 으로 합산하지 않는다)
 * - 결론: 양적 OR 질적. 수동 판정이 있으면 그것이 최종이고 계산 결론도 함께 보인다
 * - 템플릿 배지는 **칸마다** 따로 붙는다 — 고친 칸만 배지가 떨어진다
 */
export default function AccountsTable({ d, meta, write }: { d: ScopingDetail; meta: ScopingMeta; write: Write }) {
  const [tab, setTab] = useState(meta.statement_types[0]?.value ?? 'BS')
  const rows = useMemo(() => d.accounts.filter((a) => a.statement_type === tab), [d.accounts, tab])
  const quantApplies = meta.quant_applicable.includes(tab)
  const confirmed = d.status === 'confirmed'
  const policyLabel = `${d.policy.threshold} ${d.policy.comparison === 'gt' ? '초과' : '이상'}`

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-1">
        {meta.statement_types.map((t) => {
          const n = d.accounts.filter((a) => a.statement_type === t.value)
          const y = n.filter((a) => (confirmed ? a.snapshot_final : a.final) === 'Y').length
          return (
            <button key={t.value} type="button" onClick={() => setTab(t.value)}
              className={cn('rounded-md border px-3 py-1 text-sm',
                tab === t.value ? 'border-transparent bg-primary text-primary-foreground' : 'hover:bg-accent')}>
              {t.label} <span className="text-xs opacity-80">유의 {y}/{n.length}</span>
            </button>
          )
        })}
        <span className="ml-auto text-xs text-muted-foreground">
          질적 유의 기준: 평균 {policyLabel} · H=3 M=2 L=1
          {!quantApplies && ' · 이 표는 질적 판정만으로 결론을 냅니다'}
        </span>
      </div>

      <div className="overflow-x-auto rounded-md border">
        <table className="w-full text-xs">
          <thead className="bg-muted/40 text-muted-foreground">
            <tr>
              <th className="px-2 py-1 text-left">계정</th>
              {quantApplies && <th className="px-1 text-right">당기 금액(원)</th>}
              <th className="px-1">양적</th>
              {meta.qual_factors.map((f, i) => (
                <th key={f.value} className="w-10 px-0.5" title={f.label}>{i + 1}</th>
              ))}
              <th className="px-1">평균</th>
              <th className="px-1">질적</th>
              <th className="px-1">결론</th>
              <th className="px-2 text-left">판단 근거 · 수동 판정</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((a, idx) => (
              <AccountRow key={a.id} a={a} d={d} meta={meta} write={write} quantApplies={quantApplies}
                showGroup={idx === 0 || rows[idx - 1].group_label !== a.group_label} confirmed={confirmed} />
            ))}
          </tbody>
        </table>
      </div>
      <p className="text-xs text-muted-foreground">
        열 번호는 질적 요소 순서입니다 — 머리글에 마우스를 올리면 요소 이름이 보입니다.
        {confirmed && ' 확정 상태에서는 결론 칸이 확정 당시 판단(스냅샷)을 보여줍니다.'}
      </p>
    </div>
  )
}

function AccountRow({
  a, d, meta, write, quantApplies, showGroup, confirmed,
}: {
  a: ScopingAccount; d: ScopingDetail; meta: ScopingMeta; write: Write
  quantApplies: boolean; showGroup: boolean; confirmed: boolean
}) {
  const editable = d.can_edit
  const path = `/${d.id}/accounts/${a.id}`
  const [basis, setBasis] = useState(a.qual_basis ?? '')

  const setManual = () => {
    const next = window.prompt(
      a.manual_conclusion
        ? `수동 판정(${a.manual_conclusion})을 해제하려면 빈칸, 바꾸려면 Y 또는 N 을 입력하세요`
        : `계산 결론은 ${a.computed ?? '미평가'} 입니다. 수동 판정(Y/N)을 입력하세요`,
      a.manual_conclusion ?? '',
    )
    if (next === null) return
    const v = next.trim().toUpperCase()
    if (v === '') return write('patch', path, { manual_conclusion: null })
    if (v !== 'Y' && v !== 'N') return window.alert('Y 또는 N 만 입력할 수 있습니다')
    const reason = window.prompt('수동 판정 사유를 입력하세요 (필수)', a.manual_reason ?? '')
    if (!reason?.trim()) return window.alert('수동 판정에는 사유가 필요합니다')
    write('patch', path, { manual_conclusion: v, manual_reason: reason })
  }

  const shown = confirmed ? a.snapshot_final : a.final
  return (
    <>
      {showGroup && a.group_label && (
        <tr className="bg-muted/20">
          <td colSpan={99} className="px-2 py-0.5 text-[11px] font-semibold text-muted-foreground">{a.group_label}</td>
        </tr>
      )}
      <tr className="border-t align-top">
        <td className="px-2 py-1 font-medium">{a.name}</td>
        {quantApplies && (
          <td className="px-1 py-1 text-right">
            <CommitInput value={a.current_amount} format={(v) => (v === null ? '' : v.toLocaleString('ko-KR'))}
              parse={parseWon} disabled={!editable} className="w-32"
              onCommit={(v) => write('patch', path, { current_amount: v })} />
          </td>
        )}
        <td className="px-1 py-1 text-center"><JudgementBadge value={a.quant} /></td>
        {meta.qual_factors.map((f) => (
          <td key={f.value} className="px-0.5 py-1 text-center">
            <select
              value={a.ratings[f.value] ?? ''} disabled={!editable}
              onChange={(e) => write('patch', path, { ratings: { [f.value]: e.target.value || null } })}
              className={cn('h-6 rounded border bg-background text-[11px]',
                a.badges[`ratings.${f.value}`] === 'template' && 'border-dashed border-sky-300 bg-sky-50')}
              title={`${f.label}${a.badges[`ratings.${f.value}`] === 'template' ? ' · 템플릿 값' : ''}`}
            >
              <option value="">—</option>
              {meta.ratings.map((r) => <option key={r.value} value={r.value}>{r.value}</option>)}
            </select>
          </td>
        ))}
        <td className="px-1 py-1 text-center tabular-nums">{a.qual_average ? Number(a.qual_average).toFixed(1) : '—'}</td>
        <td className="px-1 py-1 text-center"><JudgementBadge value={a.qual} /></td>
        <td className="px-1 py-1 text-center">
          <JudgementBadge value={shown} />
          {a.manual_conclusion && (
            <div className="text-[10px] text-muted-foreground" title={`수동 판정 사유: ${a.manual_reason ?? ''}`}>
              수동 · 계산 {a.computed ?? '미평가'}
            </div>
          )}
        </td>
        <td className="px-2 py-1">
          <textarea value={basis} disabled={!editable} rows={1} onChange={(e) => setBasis(e.target.value)}
            onBlur={() => basis !== (a.qual_basis ?? '') && write('patch', path, { qual_basis: basis || null })}
            className="w-64 resize-y rounded border bg-background px-1 text-[11px] disabled:bg-muted/40" />
          <TemplateBadge origin={a.badges.qual_basis} />
          <div>
            {editable && (
              <button type="button" onClick={setManual} className="text-[11px] text-muted-foreground underline">
                {a.manual_conclusion ? '수동 판정 변경' : '수동 판정'}
              </button>
            )}
            {a.manual_conclusion && <TemplateBadge origin={a.badges.manual} />}
          </div>
        </td>
      </tr>
    </>
  )
}
