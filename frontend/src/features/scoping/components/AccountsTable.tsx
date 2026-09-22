import { useMemo, useState } from 'react'
import { cn } from '@/lib/utils'
import type { ScopingAccount, ScopingDetail, ScopingMeta } from '../types'
import {
  AutoTextarea, CommitInput, ConfirmToggle, JudgementBadge, TemplateBadge, changeText, originFieldClass, parseWon,
} from './bits'

type Write = (method: 'post' | 'patch' | 'delete', path: string, body?: unknown) => void
const wonFmt = (v: number | null) => (v === null ? '' : v.toLocaleString('ko-KR'))

/**
 * 계정 평가 (ADR-0034 §2.4) — 재무제표 종류별 탭.
 *
 * - 양적: |기준 금액| ≥ 수행중요성. **기준 금액은 직전 연도 결산 확정 금액**(FY = 기준 연도, 6-1b §3.4).
 *   전년 금액은 비교용 — 증감률은 질적 6번 요소의 근거일 뿐 양적 판정에 쓰지 않는다.
 *   **주석·현금흐름은 "해당 없음"**(원천 각주) — 금액칸도 두지 않는다
 * - 질적: 10요소 H/M/L 평균이 기준값 이상. **하나라도 비면 미평가**(0 으로 합산하지 않는다)
 * - 결론: 양적 OR 질적. 수동 판정이 있으면 그것이 최종이고 계산 결론도 함께 보인다
 * - 배지는 **칸마다** 따로 붙는다. 줄 끝 "확인"은 그 줄의 템플릿 값에 동의한다는 표시다(6-1b)
 */
export default function AccountsTable({ d, meta, write }: { d: ScopingDetail; meta: ScopingMeta; write: Write }) {
  const [tab, setTab] = useState(meta.statement_types[0]?.value ?? 'BS')
  const rows = useMemo(() => d.accounts.filter((a) => a.statement_type === tab), [d.accounts, tab])
  const quantApplies = meta.quant_applicable.includes(tab)
  const confirmed = d.status === 'confirmed'
  const policyLabel = `${d.policy.threshold} ${meta.qual_comparisons.find((o) => o.value === d.policy.comparison)?.label ?? ''}`
  const pending = rows.filter((a) => Object.values(a.badges).includes('template')).length

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
          {pending > 0 && ` · 이 탭에서 아직 검토하지 않은 줄 ${pending}개`}
        </span>
      </div>

      <div className="overflow-x-auto rounded-md border">
        <table className="w-full text-xs">
          <thead className="bg-muted/40 text-muted-foreground">
            <tr>
              <th className="min-w-[9rem] px-2 py-1 text-left">계정</th>
              {quantApplies && (
                <>
                  <th className="px-1 text-right">기준 금액<br />(FY{d.base_fiscal_year} 결산)</th>
                  <th className="px-1 text-right">전년 금액<br />(FY{d.base_fiscal_year - 1})</th>
                  <th className="px-1 text-right" title="(기준 − 전년) / |전년| — 비교용, 양적 판정에 쓰지 않습니다">증감률</th>
                </>
              )}
              <th className="px-1">양적</th>
              {meta.qual_factors.map((f, i) => (
                <th key={f.value} className="w-10 px-0.5" title={f.label}>{i + 1}</th>
              ))}
              <th className="px-1">평균</th>
              <th className="px-1">질적</th>
              <th className="px-1">결론</th>
              <th className="min-w-[22rem] px-2 text-left">판단 근거 · 수동 판정</th>
              <th className="px-1">검토</th>
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
        점선 하늘색 칸은 아직 검토하지 않은 템플릿 값, 초록 칸은 검토하고 동의한 값입니다.
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
  const [open, setOpen] = useState(false)

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
  const long = (a.qual_basis ?? '').length > 120 || (a.manual_reason ?? '').length > 80
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
          <>
            <td className="px-1 py-1 text-right">
              <CommitInput value={a.current_amount} format={wonFmt} parse={parseWon} disabled={!editable} className="w-32"
                onCommit={(v) => write('patch', path, { current_amount: v })} />
            </td>
            <td className="px-1 py-1 text-right">
              <CommitInput value={a.prior_amount} format={wonFmt} parse={parseWon} disabled={!editable} className="w-32"
                onCommit={(v) => write('patch', path, { prior_amount: v })} />
            </td>
            <td className="px-1 py-1 text-right tabular-nums text-muted-foreground">{changeText(a.change_rate)}</td>
          </>
        )}
        <td className="px-1 py-1 text-center"><JudgementBadge value={a.quant} /></td>
        {meta.qual_factors.map((f) => {
          const origin = a.badges[`ratings.${f.value}`]
          return (
            <td key={f.value} className="px-0.5 py-1 text-center">
              <select
                value={a.ratings[f.value] ?? ''} disabled={!editable}
                onChange={(e) => write('patch', path, { ratings: { [f.value]: e.target.value || null } })}
                className={cn('h-6 rounded border bg-background text-[11px]', originFieldClass(origin))}
                title={`${f.label}${origin === 'template' ? ' · 템플릿 값' : origin === 'confirmed' ? ' · 확인됨' : ''}`}
              >
                <option value="">—</option>
                {meta.ratings.map((r) => <option key={r.value} value={r.value}>{r.value}</option>)}
              </select>
            </td>
          )
        })}
        <td className="px-1 py-1 text-center tabular-nums">{a.qual_average ? Number(a.qual_average).toFixed(1) : '—'}</td>
        <td className="px-1 py-1 text-center"><JudgementBadge value={a.qual} /></td>
        <td className="px-1 py-1 text-center">
          <JudgementBadge value={shown} />
          {a.manual_conclusion && (
            <div className="text-[10px] text-muted-foreground">수동 · 계산 {a.computed ?? '미평가'}</div>
          )}
        </td>
        <td className="px-2 py-1">
          <div className={cn(!open && long && 'max-h-24 overflow-hidden')}>
            <div className={cn('rounded', originFieldClass(a.badges.qual_basis))}>
              <AutoTextarea value={a.qual_basis ?? ''} disabled={!editable} placeholder="판단 근거"
                onCommit={(v) => write('patch', path, { qual_basis: v || null })} />
            </div>
            {a.manual_conclusion && (
              <div className={cn('mt-1 rounded border px-1.5 py-0.5 text-[11px] leading-snug', originFieldClass(a.badges.manual))}>
                <span className="font-semibold">수동 판정 {a.manual_conclusion}</span> — {a.manual_reason}
                <TemplateBadge origin={a.badges.manual} />
              </div>
            )}
          </div>
          <div className="mt-0.5 flex gap-2">
            {long && (
              <button type="button" onClick={() => setOpen(!open)} className="text-[11px] text-muted-foreground underline">
                {open ? '접기' : '전체 보기'}
              </button>
            )}
            {editable && (
              <button type="button" onClick={setManual} className="text-[11px] text-muted-foreground underline">
                {a.manual_conclusion ? '수동 판정 변경' : '수동 판정'}
              </button>
            )}
          </div>
        </td>
        <td className="px-1 py-1 text-center">
          <ConfirmToggle origins={Object.values(a.badges)} disabled={!editable}
            onConfirm={(undo) => write('post', `/${d.id}/confirm`, { scope: 'account', target_id: a.id, undo })} />
        </td>
      </tr>
    </>
  )
}
