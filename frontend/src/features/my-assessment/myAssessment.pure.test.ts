import { describe, expect, it } from 'vitest'
import {
  canDeleteSample,
  matchesOwner,
  matchesRole,
  OWNER_ALL,
  OWNER_NONE,
  ownerOptions,
  listToMethods,
  methodsLabel,
  progressText,
  sampleDone,
  sampleMissing,
  submitBlockers,
  summarize,
} from './myAssessment.pure'
import type { SampleRead, WorklistRow } from './types'

const smp = (p: Partial<SampleRead> = {}): SampleRead => ({
  id: 's', activity_id: 'a', seq: 1, label: null, sampled_on: null, result: null, note: null, evidence: [], ...p,
})
const ev = [{ link_id: 'l', file_id: 'f', filename: 'x.pdf', title: null }]
const full = (seq: number) => smp({ seq, label: `전표-${seq}`, result: 'pass', evidence: ev })

describe('샘플 완료 판정 — 서버 _sample_done 과 같은 규칙', () => {
  it('식별·결과·증빙이 다 있어야 완료', () => {
    expect(sampleDone(full(1))).toBe(true)
    expect(sampleDone(smp({ label: 'a', result: 'pass' }))).toBe(false)
    expect(sampleDone(smp({ label: '  ', result: 'pass', evidence: ev }))).toBe(false)
    expect(sampleMissing(smp())).toEqual(['샘플 식별', '결과', '증빙'])
  })
})

describe('제출 막는 이유 — 적게 제출 불가(마스터 결정)', () => {
  it('필요 수 미달', () => {
    expect(submitBlockers({ result: 'pass', samples: [full(1), smp({ seq: 2 })] }, 2)).toEqual(['필요 샘플 2건 중 1건 완료'])
  })
  it('필요 수를 채웠어도 빈 추가 줄이 있으면 막는다', () => {
    expect(submitBlockers({ result: 'pass', samples: [full(1), full(2), smp({ seq: 3 })] }, 2))
      .toEqual(['샘플 3번이 비어 있음 — 채우거나 줄을 지우세요'])
  })
  it('결론이 없으면 막는다', () => {
    expect(submitBlockers({ result: null, samples: [full(1)] }, 1)).toEqual(['테스트 결론 미선택'])
    expect(submitBlockers({ result: 'pass', samples: [full(1)] }, 1)).toEqual([])
  })
  it('필요 수 아래로 줄 삭제 불가', () => {
    expect(canDeleteSample(2, 2)).toBe(false)
    expect(canDeleteSample(3, 2)).toBe(true)
  })
})

describe('테스트 방법 — 원천 순서로 저장', () => {
  it('체크 순서와 무관', () => {
    expect(listToMethods(['reperformance', 'inquiry'])).toBe('inquiry,reperformance')
    expect(listToMethods([])).toBeNull()
    expect(methodsLabel('inquiry,inspection')).toBe('질문, 문서검사')
    expect(methodsLabel(null)).toBe('-')
  })
})

describe('목록 집계', () => {
  const row = (p: Partial<WorklistRow>): WorklistRow => ({
    control_id: 'c', control_code: null, control_name: null, process_code: null, frequency: null, auto_manual: null,
    owner_id: 'u', owner_name: null, my_roles: [], activity_kind: 'test', required_samples: 1, sample_basis: '',
    rcm_test_methods: null, rcm_population: null, rcm_test_procedure: null, state: 'not_started', activity_id: null,
    activity_count: 0, samples_done: 0, evidence_count: 0, pending_stages: [], can_approve: [], ...p,
  })
  it('상태별 건수·필요 샘플 합계·미배정', () => {
    const s = summarize([row({ required_samples: 7 }), row({ state: 'draft', required_samples: 2, owner_id: null })])
    expect(s).toEqual({ total: 2, by: { not_started: 1, draft: 1, submitted: 0, approved: 0 }, samples: 9, unassigned: 1 })
  })
  it('진행 표시 — 추가 샘플은 필요 수를 넘겨 보이지 않는다', () => {
    expect(progressText({ state: 'draft', samples_done: 3, required_samples: 2 })).toBe('2/2')
    expect(progressText({ state: 'not_started', samples_done: 0, required_samples: 5 })).toBe('0/5')
  })
})

describe('역할·통제책임자 거르기', () => {
  const r = (my_roles: string[], owner_id: string | null = 'u1', owner_name: string | null = '갑') => ({ my_roles, owner_id, owner_name })
  it('작성할 것 = 통제책임자, 승인할 것 = 평가자·부서승인자', () => {
    expect(matchesRole(r(['control_owner']), 'write')).toBe(true)
    expect(matchesRole(r(['assessor']), 'write')).toBe(false)
    expect(matchesRole(r(['assessor']), 'approve')).toBe(true)
    expect(matchesRole(r(['dept_approver']), 'approve')).toBe(true)
    expect(matchesRole(r(['control_owner']), 'all')).toBe(true)
  })
  it('통제책임자 선택지 — 이름순·건수, 미배정은 따로', () => {
    const rows = [r([], 'u2', '을'), r([], 'u1', '갑'), r([], 'u2', '을'), r([], null, null)]
    expect(ownerOptions(rows)).toEqual([{ id: 'u1', name: '갑', count: 1 }, { id: 'u2', name: '을', count: 2 }])
    expect(rows.filter((x) => matchesOwner(x, OWNER_NONE))).toHaveLength(1)
    expect(rows.filter((x) => matchesOwner(x, 'u2'))).toHaveLength(2)
    expect(rows.filter((x) => matchesOwner(x, OWNER_ALL))).toHaveLength(4)
  })
})
