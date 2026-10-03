import { Fragment, useEffect, useMemo, useRef, useState } from 'react'
import { toast } from 'sonner'
import { Check, ChevronDown, ChevronRight } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { ScopingAccount, ScopingDetail, ScopingMeta } from '../types'
import { QUAL_SHORT, qualRuleText } from '../qualFactors.pure'
import QualFactorGuide from './QualFactorGuide'
import {
  FILTER_LABELS, SORT_LABELS, filterRows, sortRows, type AccountFilter, type AccountSort,
} from '../accountView.pure'
import { groupRows, groupStatus, type GroupStatus } from '../accountGroups.pure'
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
  // 보기(필터·정렬) — 화면 상태로만. 저장하지 않으므로 새로고침하면 전체·원래 순서로 돌아간다
  const [filter, setFilter] = useState<AccountFilter>('all')
  const [sort, setSort] = useState<AccountSort>('default')
  const shown = useMemo(() => sortRows(filterRows(rows, filter, confirmed), sort), [rows, filter, sort, confirmed])
  const grouped = sort === 'default'   // 정렬하면 재무제표 그룹 순서가 깨지므로 묶음 없이 평평하게
  // ── 묶음 카드(2026-10-03) — 상태는 필터와 무관하게 탭 전체 기준. 접힘은 화면 상태(새로고침 시 다시 '완료만 접힘')
  const statusByLabel = useMemo(() => {
    const m = new Map<string, GroupStatus>()
    for (const g of groupRows(rows, confirmed)) m.set(g.label, g.status)
    return m
  }, [rows, confirmed])
  const groups = useMemo(() => (grouped ? groupRows(shown, confirmed) : []), [grouped, shown, confirmed])
  const [collapsed, setCollapsed] = useState<Record<string, boolean>>({})
  const prevComplete = useRef<Record<string, boolean>>({})
  useEffect(() => {
    const updates: Record<string, boolean> = {}
    const done: string[] = []
    statusByLabel.forEach((st, label) => {
      const key = `${tab}:${label}`
      const before = prevComplete.current[key]
      if (before === undefined) {
        if (!(key in collapsed)) updates[key] = st.complete   // 처음 볼 때: 완료된 묶음만 접는다
      } else if (!before && st.complete) {
        updates[key] = true                                     // 방금 완료 → 접고 알린다
        done.push(label)
      }
      prevComplete.current[key] = st.complete
    })
    if (Object.keys(updates).length) setCollapsed((c) => ({ ...c, ...updates }))
    done.forEach((label) => toast.success(`'${label}' 묶음 평가를 마쳤습니다 — 접어 두었습니다`))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [statusByLabel, tab])
  const isCollapsed = (label: string) => !!collapsed[`${tab}:${label}`]
  const setAll = (v: boolean) =>
    setCollapsed((c) => ({ ...c, ...Object.fromEntries([...statusByLabel.keys()].map((l) => [`${tab}:${l}`, v])) }))
  const completeGroups = [...statusByLabel.values()].filter((g) => g.complete).length
  const tabStatus = groupStatus(rows, confirmed)
  // 기준·전년 금액이 모두 0(또는 전년 없음)인데 아직 해당 없음이 아닌 줄 — 이 탭에서만
  const zeroRows = quantApplies
    ? rows.filter((a) => !a.not_applicable && a.current_amount === 0 && (a.prior_amount === 0 || a.prior_amount === null))
    : []
  const markZero = () => {
    const reason = window.prompt(
      `기준·전년 금액이 모두 0 인 계정 ${zeroRows.length}개를 '해당 없음'으로 지정합니다 — 판정에서 빠지고 이력에 남습니다.\n사유를 입력하세요(필수)`,
      '기준·전년 금액 0 — 해당 거래 없음')
    if (!reason?.trim()) return
    write('post', `/${d.id}/accounts/not-applicable`, { account_ids: zeroRows.map((a) => a.id), value: true, reason: reason.trim() })
  }

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

      <QualFactorGuide factors={meta.qual_factors} rule={qualRuleText(d.policy)} />
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <span className="font-medium">보기</span>
        <select aria-label="계정 필터" value={filter} onChange={(e) => setFilter(e.target.value as AccountFilter)}
          className="h-9 rounded-md border bg-background py-0 pl-3 pr-8 text-sm">
          {(Object.keys(FILTER_LABELS) as AccountFilter[]).map((k) => <option key={k} value={k}>{FILTER_LABELS[k]}</option>)}
        </select>
        <select aria-label="정렬" value={sort} onChange={(e) => setSort(e.target.value as AccountSort)}
          className="h-9 rounded-md border bg-background py-0 pl-3 pr-8 text-sm">
          {(Object.keys(SORT_LABELS) as AccountSort[]).map((k) => <option key={k} value={k}>{SORT_LABELS[k]}</option>)}
        </select>
        <span className="text-muted-foreground">{shown.length} / {rows.length}개 표시</span>
        {grouped && (
          <>
            <span className="rounded-full bg-accent px-2.5 py-0.5 text-xs font-medium text-accent-foreground">
              묶음 완료 {completeGroups}/{statusByLabel.size} · 계정 판정 {tabStatus.decided}/{tabStatus.total}
            </span>
            <button type="button" className="text-xs text-muted-foreground underline-offset-2 hover:underline" onClick={() => setAll(false)}>모두 펼치기</button>
            <button type="button" className="text-xs text-muted-foreground underline-offset-2 hover:underline" onClick={() => setAll(true)}>모두 접기</button>
          </>
        )}
        {d.can_edit && zeroRows.length > 0 && (
          <button type="button" onClick={markZero}
            className="ml-auto rounded-md border px-3 py-1.5 text-xs hover:border-primary/40 hover:bg-accent">
            금액 0 계정 {zeroRows.length}개 일괄 '해당 없음'
          </button>
        )}
        {(filter !== 'all' || sort !== 'default') && (
          <button type="button" className="text-xs text-primary underline-offset-2 hover:underline"
            onClick={() => { setFilter('all'); setSort('default') }}>초기화</button>
        )}
      </div>
      <div className="overflow-x-auto rounded-md border">
        <table className="w-full text-xs">
          <thead className="bg-muted/40 text-muted-foreground">
            <tr>
              <th className="min-w-[9rem] px-2 py-1 text-left">계정</th>
              {quantApplies && (
                <>
                  <th className="min-w-[8.75rem] px-1 text-right">기준 금액<br />(FY{d.base_fiscal_year} 결산)</th>
                  <th className="min-w-[8.75rem] px-1 text-right">전년 금액<br />(FY{d.base_fiscal_year - 1})</th>
                  <th className="min-w-[4rem] px-1 text-right" title="(기준 − 전년) / |전년| — 비교용, 양적 판정에 쓰지 않습니다">증감률</th>
                </>
              )}
              <th className="min-w-[3.5rem] px-1">양적</th>
              {meta.qual_factors.map((f, i) => (
                <th key={f.value} className="w-10 min-w-[2.9rem] px-0.5 align-bottom leading-tight" title={`${i + 1}. ${f.label}`}>
                  <span className="block text-sm font-bold text-foreground">{i + 1}</span>
                  <span className="block whitespace-nowrap text-[10px] font-medium">{QUAL_SHORT[f.value] ?? ''}</span>
                </th>
              ))}
              <th className="min-w-[3rem] px-1">평균</th>
              <th className="min-w-[3.5rem] px-1">질적</th>
              <th className="min-w-[3.5rem] px-1">결론</th>
              <th className="min-w-[22rem] px-2 text-left">판단 근거 · 수동 판정</th>
              <th className="px-1">검토</th>
            </tr>
          </thead>
          <tbody>
            {shown.length === 0 && (
              <tr><td colSpan={99} className="px-3 py-6 text-center text-sm text-muted-foreground">조건에 맞는 계정이 없습니다</td></tr>
            )}
            {grouped ? groups.map((g, gi) => {
              const st = statusByLabel.get(g.label) ?? g.status
              const closed = isCollapsed(g.label)
              return (
                <Fragment key={g.key}>
                  {gi > 0 && <tr aria-hidden="true"><td colSpan={99} className="h-3 border-0 bg-background p-0" /></tr>}
                  <GroupHeader label={g.label} st={st} closed={closed}
                    onToggle={() => setCollapsed((c) => ({ ...c, [`${tab}:${g.label}`]: !closed }))} />
                  {!closed && g.rows.map((a) => (
                    <AccountRow key={a.id} a={a} d={d} meta={meta} write={write} quantApplies={quantApplies}
                      showGroup={false} confirmed={confirmed} />
                  ))}
                </Fragment>
              )
            }) : shown.map((a) => (
              <AccountRow key={a.id} a={a} d={d} meta={meta} write={write} quantApplies={quantApplies}
                showGroup={false} confirmed={confirmed} />
            ))}
          </tbody>
        </table>
      </div>
      <p className="text-xs text-muted-foreground">
        점선 칸은 아직 검토하지 않은 템플릿 값, 초록 칸은 검토하고 동의한 값입니다.
        {confirmed && ' 확정 상태에서는 결론 칸이 확정 당시 판단(스냅샷)을 보여줍니다.'}
      </p>
    </div>
  )
}

/** 묶음 카드 머리 — 이름·계정 수·진행 막대·상태별 건수. 누르면 접고 편다 */
function GroupHeader({ label, st, closed, onToggle }: { label: string; st: GroupStatus; closed: boolean; onToggle: () => void }) {
  return (
    <tr className={cn('cursor-pointer select-none border-t-2', st.complete ? 'border-success/40 bg-success/5' : 'border-primary/30 bg-accent/60')}
      onClick={onToggle}>
      <td colSpan={99} className="px-3 py-2">
        {/* 표가 가로로 넓어도 머리 내용은 보이는 폭 안에 — 왼쪽에 붙여 둔다 */}
        <div className="sticky left-3 flex w-max max-w-[calc(100vw-22rem)] flex-wrap items-center gap-x-4 gap-y-1.5">
          <span className="flex items-center gap-1.5 text-sm font-semibold text-foreground">
            {closed ? <ChevronRight className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
            {label}
            <span className="font-normal text-muted-foreground">· {st.total}개</span>
            {st.complete && <span className="ml-1 inline-flex items-center gap-1 rounded-full bg-success/15 px-2 py-0.5 text-xs font-semibold text-success"><Check className="h-3.5 w-3.5" />완료</span>}
          </span>
          <span className="flex items-center gap-2">
            <span className="h-2 w-36 overflow-hidden rounded-full bg-muted">
              <span className={cn('block h-full rounded-full', st.complete ? 'bg-success' : 'bg-primary')} style={{ width: `${st.percent}%` }} />
            </span>
            <span className="w-28 text-xs tabular-nums text-muted-foreground">판정 {st.decided}/{st.total} ({st.percent}%)</span>
          </span>
          <span className="flex flex-wrap items-center gap-1.5 text-xs">
            <Chip tone="y" n={st.Y} label="유의 Y" />
            <Chip tone="n" n={st.N} label="비유의 N" />
            <Chip tone="na" n={st.na} label="해당 없음" />
            <Chip tone="warn" n={st.unevaluated} label="미평가" />
            <Chip tone="warn" n={st.pendingRows} label="검토 안 한 값" />
          </span>
        </div>
      </td>
    </tr>
  )
}

function Chip({ tone, n, label }: { tone: 'y' | 'n' | 'na' | 'warn'; n: number; label: string }) {
  if (n === 0 && (tone === 'warn' || tone === 'na')) return null
  return (
    <span className={cn('rounded-full border px-2 py-0.5 font-medium',
      tone === 'y' && n > 0 && 'border-red-200 bg-red-50 text-red-700',
      tone === 'y' && n === 0 && 'border-border bg-background text-muted-foreground',
      tone === 'n' && 'border-border bg-background text-muted-foreground',
      tone === 'na' && 'border-border bg-muted text-muted-foreground',
      tone === 'warn' && 'border-warning/40 bg-warning/10 text-warning')}>
      {label} {n}
    </span>
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
  // 해당 없음 — 판정에서 빼는 것이라 사유를 받는다(이력에 남는다)
  const toggleNa = () => {
    if (a.not_applicable) {
      if (window.confirm(`'${a.name}' 의 해당 없음을 해제할까요? 다시 판정 대상이 됩니다.`)) {
        write('patch', path, { not_applicable: false })
      }
      return
    }
    const reason = window.prompt(`'${a.name}' 을(를) 해당 없음으로 지정합니다 — 판정에서 빠집니다. 사유를 입력하세요(필수)`,
      a.current_amount === 0 ? '금액 0 — 해당 거래 없음' : '')
    if (!reason?.trim()) return
    write('patch', path, { not_applicable: true, na_reason: reason.trim() })
  }

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
      <tr className={cn('border-t align-top', a.not_applicable && 'bg-muted/30 text-muted-foreground')}>
        <td className="px-2 py-1 font-medium">
          {a.name}
          {a.not_applicable && (
            <span className="mt-0.5 block text-[11px] font-normal" title={a.na_reason ?? ''}>해당 없음 · {a.na_reason}</span>
          )}
        </td>
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
                value={a.ratings[f.value] ?? ''} disabled={!editable || !!a.not_applicable}
                onChange={(e) => write('patch', path, { ratings: { [f.value]: e.target.value || null } })}
                // 고정 높이 칸에 폼 기본 여백(위아래 0.5rem·오른쪽 2.5rem)이 붙으면 글자가 밀려 안 보인다 — 여백을 직접 준다
                className={cn('h-7 w-full min-w-[2.6rem] rounded border bg-background bg-[length:0.9rem] bg-[position:right_0.15rem_center] py-0 pl-1.5 pr-4 text-xs font-semibold leading-none', originFieldClass(origin))}
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
            {editable && !a.not_applicable && (
              <button type="button" onClick={setManual} className="text-[11px] text-muted-foreground underline">
                {a.manual_conclusion ? '수동 판정 변경' : '수동 판정'}
              </button>
            )}
            {editable && (
              <button type="button" onClick={toggleNa} className="text-[11px] text-muted-foreground underline">
                {a.not_applicable ? '해당 없음 해제' : '해당 없음'}
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
