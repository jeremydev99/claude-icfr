import { describe, expect, it } from 'vitest'
import { effective, groupByProcess, matches, pkey, toChanges, type MatrixControl, type MatrixProcess, type RoleMatrixData } from './roleMatrix.pure'

const proc = (id: string, owner?: string): MatrixProcess => ({
  id, code: id, name: id,
  roles: { control_owner: owner ? { user_id: owner, user_name: owner } : null, dept_approver: null, assessor: null },
})
const ctrl = (id: string, pid: string | null, extra: Partial<MatrixControl> = {}): MatrixControl => ({
  id, code: id, name: id, process_id: pid, process_code: pid, is_key_control: false, owner_name: null, iuc_count: 0, euc_count: 0,
  roles: [
    { role_name: 'control_owner', user_id: null, user_name: null, source: 'none' },
    { role_name: 'dept_approver', user_id: null, user_name: null, source: 'none' },
    { role_name: 'assessor', user_id: null, user_name: null, source: 'none' },
  ],
  conflicts: [], dept_approval_skipped: false, ...extra,
})

describe('roleMatrix', () => {
  it('작성 중 값 → 통제 예외 → 프로세스 기본값 순서로 보인다', () => {
    const procs = new Map([['P', proc('P', 'u1')]])
    const c = ctrl('C1', 'P')
    expect(effective(c, 'control_owner', {}, procs)).toMatchObject({ userId: 'u1', source: 'process', overridden: false })
    expect(effective(c, 'control_owner', { [pkey('control', 'C1', 'control_owner')]: 'u2' }, procs))
      .toMatchObject({ userId: 'u2', source: 'pending', overridden: true })
    // 프로세스 기본값을 바꾸는 중이면 그 값이 보인다
    expect(effective(c, 'control_owner', { [pkey('process', 'P', 'control_owner')]: 'u3' }, procs)).toMatchObject({ userId: 'u3' })
    // 통제 예외를 지우면 기본값으로
    const over = ctrl('C2', 'P', { roles: [{ role_name: 'control_owner', user_id: 'u9', user_name: 'x', source: 'control' },
      ...ctrl('x', null).roles.slice(1)] })
    expect(effective(over, 'control_owner', { [pkey('control', 'C2', 'control_owner')]: null }, procs)).toMatchObject({ userId: 'u1' })
  })
  it('서버와 같은 값은 보내지 않는다', () => {
    const data: RoleMatrixData = { processes: [proc('P', 'u1')], controls: [ctrl('C1', 'P')], users: [] }
    expect(toChanges({ [pkey('process', 'P', 'control_owner')]: 'u1', [pkey('control', 'C1', 'assessor')]: 'u2' }, data))
      .toEqual([{ scope: 'control', target_id: 'C1', role_name: 'assessor', user_id: 'u2' }])
  })
  it('필터·묶음', () => {
    const c = ctrl('C1', 'P', { euc_count: 1 })
    expect(matches(c, 'unassigned', '')).toBe(true)
    expect(matches(c, 'euc', '')).toBe(true)
    expect(matches(c, 'iuc', '')).toBe(false)
    expect(matches(c, 'all', 'zz')).toBe(false)
    const g = groupByProcess([ctrl('B', 'P'), ctrl('A', 'P'), ctrl('X', null)], [proc('P')])
    expect(g.map((x) => x.process?.id ?? null)).toEqual(['P', null])
    expect(g[0].controls.map((x) => x.id)).toEqual(['A', 'B'])
  })
})
