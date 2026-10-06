// 역할 일괄 배정 표 순수 로직 — `roleMatrix.test.ts`. 판정(겸직·정책)은 서버.

export type RoleName = 'control_owner' | 'dept_approver' | 'assessor'
export const ROLES: RoleName[] = ['control_owner', 'dept_approver', 'assessor']
export const ROLE_LABEL: Record<RoleName, string> = { control_owner: '통제책임자', dept_approver: '부서승인자', assessor: '평가자' }

export interface ResolvedRole {
  role_name: RoleName
  user_id: string | null
  user_name: string | null
  source: 'control' | 'process' | 'derived' | 'none'
}

export interface MatrixControl {
  id: string
  code: string | null
  name: string | null
  process_id: string | null
  process_code: string | null
  is_key_control: boolean
  owner_name: string | null
  iuc_count: number
  euc_count: number
  roles: ResolvedRole[]
  conflicts: string[]
  dept_approval_skipped: boolean
}

export interface MatrixProcess {
  id: string
  code: string
  name: string | null
  roles: Record<RoleName, { user_id: string; user_name: string | null } | null>
}

export interface RoleMatrixData {
  processes: MatrixProcess[]
  controls: MatrixControl[]
  users: { id: string; name: string }[]
}

/** 작성 중 변경 — 키 `scope:target:role` → 사람 id(null = 지움: 통제면 기본값 따름) */
export type Pending = Record<string, string | null>
export const pkey = (scope: 'process' | 'control', target: string, role: RoleName) => `${scope}:${target}:${role}`

export type Filter = 'all' | 'unassigned' | 'euc' | 'iuc' | 'key' | 'conflict'

export function matches(c: MatrixControl, f: Filter, q: string): boolean {
  const s = q.trim().toLowerCase()
  if (s && !`${c.code ?? ''} ${c.name ?? ''} ${c.owner_name ?? ''}`.toLowerCase().includes(s)) return false
  if (f === 'unassigned') return c.roles.some((r) => r.role_name !== 'dept_approver' && !r.user_id)
  if (f === 'euc') return c.euc_count > 0
  if (f === 'iuc') return c.iuc_count > 0
  if (f === 'key') return c.is_key_control
  if (f === 'conflict') return c.conflicts.length > 0
  return true
}

/** 화면에 보일 값 — 작성 중 변경을 먼저 보고, 없으면 서버 해석. 통제 예외를 지우면 프로세스 기본값(작성 중 포함)을 보인다 */
export function effective(c: MatrixControl, role: RoleName, pending: Pending, procs: Map<string, MatrixProcess>):
  { userId: string | null; source: ResolvedRole['source'] | 'pending'; overridden: boolean } {
  const ck = pkey('control', c.id, role)
  const server = c.roles.find((r) => r.role_name === role)
  if (ck in pending) {
    if (pending[ck]) return { userId: pending[ck], source: 'pending', overridden: true }
    return fromProcess()
  }
  if (server?.source === 'control') return { userId: server.user_id, source: 'control', overridden: true }
  return fromProcess()

  function fromProcess() {
    const pk = c.process_id ? pkey('process', c.process_id, role) : ''
    if (pk && pk in pending) return { userId: pending[pk], source: pending[pk] ? 'pending' as const : 'none' as const, overridden: false }
    const p = c.process_id ? procs.get(c.process_id)?.roles[role] : null
    if (p) return { userId: p.user_id, source: 'process' as const, overridden: false }
    if (server?.source === 'derived') return { userId: server.user_id, source: 'derived' as const, overridden: false }
    return { userId: null, source: 'none' as const, overridden: false }
  }
}

/** 저장 요청 본문 — 서버와 같은 값이면 보내지 않는다 */
export function toChanges(pending: Pending, data: RoleMatrixData) {
  const out: { scope: 'process' | 'control'; target_id: string; role_name: RoleName; user_id: string | null }[] = []
  const procs = new Map(data.processes.map((p) => [p.id, p]))
  const ctrls = new Map(data.controls.map((c) => [c.id, c]))
  for (const [k, v] of Object.entries(pending)) {
    const [scope, target, role] = k.split(':') as ['process' | 'control', string, RoleName]
    const cur = scope === 'process'
      ? procs.get(target)?.roles[role]?.user_id ?? null
      : (() => { const r = ctrls.get(target)?.roles.find((x) => x.role_name === role); return r?.source === 'control' ? r.user_id : null })()
    if ((cur ?? null) !== (v ?? null)) out.push({ scope, target_id: target, role_name: role, user_id: v })
  }
  return out
}

export function groupByProcess(controls: MatrixControl[], processes: MatrixProcess[]) {
  const by = new Map<string, MatrixControl[]>()
  for (const c of controls) by.set(c.process_id ?? '-', [...(by.get(c.process_id ?? '-') ?? []), c])
  const groups = processes.filter((p) => by.has(p.id)).map((p) => ({ process: p as MatrixProcess | null, controls: by.get(p.id)! }))
  if (by.has('-')) groups.push({ process: null, controls: by.get('-')! })
  for (const g of groups) g.controls.sort((a, b) => (a.code ?? '').localeCompare(b.code ?? ''))
  return groups
}
