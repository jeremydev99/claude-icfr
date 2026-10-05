import { describe, expect, it } from 'vitest'
import {
  accountCoverage, boardStats, buildMatrix, groupControls, linkLook, visibleAccounts,
  type BoardAccount, type BoardControl, type BoardLink,
} from './linkBoard.pure'

const ctrl = (id: string, process_code: string): BoardControl => ({
  id, code: id, name: id, process_code, process_name: `P-${process_code}`, is_key_control: false, related_accounts: null,
})
const acct = (key: string, significant: string | null = 'Y', parent_key: string | null = null): BoardAccount => ({
  key, fs_account_id: key, name: key, statement_type: 'BS', parent_key, depth: parent_key ? 1 : 0, has_children: false, significant,
})
const link = (control_id: string, account_key: string, state: BoardLink['state'] = 'active',
  remove_state: BoardLink['remove_state'] = null): BoardLink => ({
  id: `${control_id}-${account_key}`, control_id, account_key, state, remove_state, source: 'manual', match_kind: null, match_token: null,
})

describe('linkBoard', () => {
  it('통제를 프로세스별로 묶는다', () => {
    const g = groupControls([ctrl('C2', 'B'), ctrl('C1', 'A'), ctrl('C0', 'A')])
    expect(g.map((x) => x.code)).toEqual(['A', 'B'])
    expect(g[0].controls.map((c) => c.id)).toEqual(['C0', 'C1'])
  })
  it('연결 모양과 계정 커버 상태', () => {
    expect(linkLook(link('c', 'a', 'active', 'draft'))).toBe('removing')
    expect(accountCoverage([link('c', 'a', 'draft')])).toBe('pending')
    expect(accountCoverage([link('c', 'a', 'active', 'review')])).toBe('none')
    expect(accountCoverage([link('c', 'a')])).toBe('covered')
    expect(accountCoverage(undefined)).toBe('none')
  })
  it('유의만·검색 필터', () => {
    const as = [acct('현금'), acct('매출채권', 'N'), acct('미수금', null)]
    expect(visibleAccounts(as, { sigOnly: true, query: '' }).map((a) => a.key)).toEqual(['현금'])
    expect(visibleAccounts(as, { sigOnly: false, query: '매출 채권' }).map((a) => a.key)).toEqual(['매출채권'])
  })
  it('통계·행렬', () => {
    const b = {
      controls: [ctrl('C1', 'A'), ctrl('C2', 'B')],
      accounts: [acct('a1'), acct('a2'), acct('a3'), acct('n1', 'N')],
      links: [link('C1', 'a1'), link('C2', 'a1', 'draft'), link('C2', 'a2', 'review'), link('C1', 'n1', 'active', 'draft')],
    }
    const s = boardStats(b)
    expect([s.significant, s.sigCovered, s.sigPending, s.sigNone]).toEqual([3, 1, 1, 1])
    expect([s.active, s.draft, s.review, s.removing]).toEqual([1, 2, 1, 1])
    const m = buildMatrix(b)
    expect(m.processes.map((p) => p.code)).toEqual(['A', 'B'])
    const r1 = m.rows.find((r) => r.account.key === 'a1')!
    expect(r1.cells).toEqual({ A: { active: 1, pending: 0 }, B: { active: 0, pending: 1 } })
    expect(m.rows.find((r) => r.account.key === 'a3')!.active).toBe(0)
  })
})
