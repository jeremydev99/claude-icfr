/**
 * 계정 평가 묶음 — 재무제표 상위 계정(group_label)별 카드와 진행 상태. 순수 함수, `accountGroups.test.ts`.
 *
 * 완료 = 묶음의 모든 계정이 판정됨(Y·N·해당 없음) **그리고** 검토 안 한 템플릿 값이 0.
 * 판정은 했어도 템플릿 값을 아무도 안 봤으면 끝난 것이 아니다 — 감사인이 묻는 것이 "누가 봤나"다.
 */
import { conclusionOf, type ViewRow } from './accountView.pure'

export interface GroupRow extends ViewRow { group_label: string | null }

export interface GroupStatus {
  total: number
  Y: number
  N: number
  na: number
  unevaluated: number
  /** 검토 안 한 템플릿 값이 남은 계정 수(해당 없음 제외) */
  pendingRows: number
  /** 판정된 계정 수(Y·N·해당 없음) */
  decided: number
  complete: boolean
  /** 0~100 — 판정 기준 진행률 */
  percent: number
}

export interface AccountGroup<T> { key: string; label: string; rows: T[]; status: GroupStatus }

export function groupStatus(rows: ViewRow[], confirmed: boolean): GroupStatus {
  const s = { total: rows.length, Y: 0, N: 0, na: 0, unevaluated: 0, pendingRows: 0 }
  for (const r of rows) {
    const c = conclusionOf(r, confirmed)
    if (c === 'Y') s.Y += 1
    else if (c === 'N') s.N += 1
    else if (c === 'na') s.na += 1
    else s.unevaluated += 1
    if (c !== 'na' && Object.values(r.badges).includes('template')) s.pendingRows += 1
  }
  const decided = s.Y + s.N + s.na
  return {
    ...s, decided,
    complete: s.total > 0 && s.unevaluated === 0 && s.pendingRows === 0,
    percent: s.total ? Math.round((decided / s.total) * 100) : 0,
  }
}

/** 원래 순서를 유지하며 연속한 같은 group_label 을 한 묶음으로 */
export function groupRows<T extends GroupRow>(rows: T[], confirmed: boolean): AccountGroup<T>[] {
  const out: AccountGroup<T>[] = []
  for (const r of rows) {
    const label = r.group_label ?? '기타'
    const last = out[out.length - 1]
    if (last && last.label === label) last.rows.push(r)
    else out.push({ key: `${out.length}-${label}`, label, rows: [r], status: groupStatus([], confirmed) })
  }
  for (const g of out) g.status = groupStatus(g.rows, confirmed)
  return out
}
