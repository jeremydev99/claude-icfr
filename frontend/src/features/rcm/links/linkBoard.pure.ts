// 통제 ↔ 계정 연결 보드(ADR-0040) 순수 로직 — DOM·네트워크 없음. `linkBoard.test.ts`.

export interface BoardControl {
  id: string
  code: string | null
  name: string | null
  process_code: string | null
  process_name: string | null
  is_key_control: boolean
  related_accounts: string | null
}

export interface BoardAccount {
  key: string
  fs_account_id: string | null
  name: string
  statement_type: 'BS' | 'PL' | 'NOTE'
  parent_key: string | null
  depth: number
  has_children: boolean
  /** 최신 스코핑 결론 — Y | N | na | null(미평가·스코핑 없음) */
  significant: string | null
}

export type LinkState = 'draft' | 'review' | 'active'

export interface BoardLink {
  id: string
  control_id: string
  account_key: string
  state: LinkState
  remove_state: 'draft' | 'review' | null
  source: 'auto' | 'manual'
  match_kind: string | null
  match_token: string | null
}

export interface Board {
  controls: BoardControl[]
  accounts: BoardAccount[]
  links: BoardLink[]
  dismissed: number
  open_proposal: { id: string; status: string; title: string } | null
}

/** 선 모양 — 활성(실선)·작성 중(점선)·검토 중·해제 예정 */
export type LinkLook = 'active' | 'draft' | 'review' | 'removing'

export function linkLook(l: BoardLink): LinkLook {
  if (l.remove_state) return 'removing'
  return l.state
}

export const MATCH_LABEL: Record<string, string> = {
  exact: '이름 일치', alias: '다른 이름', parent: '상위 계정', partial: '이름 일부', manual: '수동',
}

export function groupControls(controls: BoardControl[]): { code: string; name: string; controls: BoardControl[] }[] {
  const m = new Map<string, { code: string; name: string; controls: BoardControl[] }>()
  for (const c of controls) {
    const code = c.process_code ?? '-'
    if (!m.has(code)) m.set(code, { code, name: c.process_name ?? '프로세스 없음', controls: [] })
    m.get(code)!.controls.push(c)
  }
  for (const g of m.values()) g.controls.sort((a, b) => (a.code ?? '').localeCompare(b.code ?? ''))
  return [...m.values()].sort((a, b) => a.code.localeCompare(b.code))
}

export function indexLinks(links: BoardLink[]) {
  const byControl = new Map<string, BoardLink[]>()
  const byAccount = new Map<string, BoardLink[]>()
  for (const l of links) {
    byControl.set(l.control_id, [...(byControl.get(l.control_id) ?? []), l])
    byAccount.set(l.account_key, [...(byAccount.get(l.account_key) ?? []), l])
  }
  return { byControl, byAccount }
}

/** 계정 연결 상태 — 확정(활성, 해제 예정 제외) / 작성 중만 / 없음 */
export function accountCoverage(links: BoardLink[] | undefined): 'covered' | 'pending' | 'none' {
  const ls = links ?? []
  if (ls.some((l) => l.state === 'active' && !l.remove_state)) return 'covered'
  if (ls.some((l) => l.state !== 'active')) return 'pending'
  return 'none'
}

/** 보이는 계정 — 유의(Y)만이면 평평하게, 검색어가 있으면 이름 포함. 트리 맥락은 상위 이름으로 보여 준다 */
export function visibleAccounts(accounts: BoardAccount[], opts: { sigOnly: boolean; query: string }): BoardAccount[] {
  const q = opts.query.trim().replace(/\s+/g, '').toLowerCase()
  return accounts.filter((a) => {
    if (opts.sigOnly && a.significant !== 'Y') return false
    if (q && !a.name.replace(/\s+/g, '').toLowerCase().includes(q)) return false
    return true
  })
}

export function parentName(accounts: BoardAccount[], a: BoardAccount): string | null {
  if (!a.parent_key) return null
  return accounts.find((x) => x.key === a.parent_key)?.name ?? null
}

export interface BoardStats {
  active: number
  draft: number
  review: number
  removing: number
  significant: number
  sigCovered: number
  sigPending: number
  sigNone: number
}

export function boardStats(b: Pick<Board, 'accounts' | 'links'>): BoardStats {
  const { byAccount } = indexLinks(b.links)
  const sig = b.accounts.filter((a) => a.significant === 'Y')
  const cov = sig.map((a) => accountCoverage(byAccount.get(a.key)))
  return {
    active: b.links.filter((l) => l.state === 'active' && !l.remove_state).length,
    draft: b.links.filter((l) => l.state === 'draft').length + b.links.filter((l) => l.remove_state === 'draft').length,
    review: b.links.filter((l) => l.state === 'review' || l.remove_state === 'review').length,
    removing: b.links.filter((l) => !!l.remove_state).length,
    significant: sig.length,
    sigCovered: cov.filter((c) => c === 'covered').length,
    sigPending: cov.filter((c) => c === 'pending').length,
    sigNone: cov.filter((c) => c === 'none').length,
  }
}

/** 행렬 — 행 = 유의 계정, 열 = 프로세스, 칸 = {확정, 작성 중} 통제 수 */
export function buildMatrix(b: Pick<Board, 'accounts' | 'links' | 'controls'>) {
  const processes = groupControls(b.controls).map((g) => ({ code: g.code, name: g.name }))
  const procOf = new Map(b.controls.map((c) => [c.id, c.process_code ?? '-']))
  const { byAccount } = indexLinks(b.links)
  const rows = b.accounts.filter((a) => a.significant === 'Y').map((a) => {
    const cells: Record<string, { active: number; pending: number }> = {}
    for (const l of byAccount.get(a.key) ?? []) {
      const p = procOf.get(l.control_id) ?? '-'
      cells[p] ??= { active: 0, pending: 0 }
      if (l.state === 'active' && !l.remove_state) cells[p].active += 1
      else if (l.state !== 'active') cells[p].pending += 1
    }
    const active = Object.values(cells).reduce((s, c) => s + c.active, 0)
    const pending = Object.values(cells).reduce((s, c) => s + c.pending, 0)
    return { account: a, cells, active, pending }
  })
  return { processes, rows }
}
