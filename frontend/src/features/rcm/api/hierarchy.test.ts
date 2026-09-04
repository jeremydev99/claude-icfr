// @vitest-environment node
// 상위 3계층 CRUD 신규 코드(어댑터/에러 핸들러/권한 seam) 단위 테스트.
// sourceEnvelope.test.ts와 동일하게 순수 로직만 검증한다 — jsdom 미설치라 렌더 테스트는 하지 않는다.
import { describe, it, expect } from 'vitest'
import { AxiosError } from 'axios'
import { toProcess, toSubProcess, toRisk } from './controlsAdapter'
import { extractHierarchyErrorMessage } from './errors'
import { canEditHierarchy } from '../permissions'

describe('toProcess / toSubProcess / toRisk', () => {
  it('ProcessItemDto를 도메인 ProcessItem으로 조립한다 (description 포함)', () => {
    const dto = {
      id: 'p1', code: 'O2C', name: '수익주기', description: '설명',
      source: 'baseline' as const, baseline_id: null, is_overridden: false,
    }
    expect(toProcess(dto)).toEqual({
      id: 'p1', code: 'O2C', name: '수익주기', description: '설명',
      envelope: { id: 'p1', source: 'baseline', baseline_id: null, is_overridden: false },
    })
  })

  it('description이 null이어도 정상 조립한다', () => {
    const dto = {
      id: 'p2', code: 'P2P', name: '구매주기', description: null,
      source: 'tenant' as const, baseline_id: null, is_overridden: false,
    }
    expect(toProcess(dto).description).toBeNull()
  })

  it('SubProcessItemDto를 도메인 SubProcessItem으로 조립한다', () => {
    const dto = {
      id: 'sp1', code: 'O2C-AR', name: '매출채권', process_id: 'p1',
      source: 'baseline' as const, baseline_id: 'p1', is_overridden: true,
    }
    expect(toSubProcess(dto)).toEqual({
      id: 'sp1', code: 'O2C-AR', name: '매출채권', process_id: 'p1',
      envelope: { id: 'sp1', source: 'baseline', baseline_id: 'p1', is_overridden: true },
    })
  })

  it('RiskItemDto를 도메인 RiskItem으로 조립한다', () => {
    const dto = {
      id: 'r1', code: 'O2C-AR-R001', description: '위험 설명', assessment_level: 'HR' as const,
      sub_process_id: 'sp1', source: 'tenant' as const, baseline_id: null, is_overridden: false,
    }
    expect(toRisk(dto)).toEqual({
      id: 'r1', code: 'O2C-AR-R001', description: '위험 설명', assessment_level: 'HR',
      sub_process_id: 'sp1',
      envelope: { id: 'r1', source: 'tenant', baseline_id: null, is_overridden: false },
    })
  })
})

function makeAxiosError(status: number, data?: unknown): AxiosError {
  const err = new AxiosError('request failed')
  err.response = { status, data, statusText: '', headers: {}, config: {} as never }
  return err
}

describe('extractHierarchyErrorMessage', () => {
  it('409는 서버 detail을 그대로 노출한다 (충돌 종류 문자열 매칭 없이)', () => {
    const err = makeAxiosError(409, { detail: "프로세스 코드 'O2C' 는 표준(baseline)에 이미 있습니다" })
    expect(extractHierarchyErrorMessage(err)).toBe("프로세스 코드 'O2C' 는 표준(baseline)에 이미 있습니다")
  })

  it('detail이 배열이면(422 검증 오류) msg를 이어붙인다', () => {
    const err = makeAxiosError(422, { detail: [{ msg: 'field required' }, { msg: 'too short' }] })
    expect(extractHierarchyErrorMessage(err)).toBe('field required, too short')
  })

  it('401은 로그인 필요 메시지로 폴백한다', () => {
    const err = makeAxiosError(401, {})
    expect(extractHierarchyErrorMessage(err)).toBe('로그인이 필요합니다')
  })

  it('404는 대상 없음 메시지로 폴백한다', () => {
    const err = makeAxiosError(404, {})
    expect(extractHierarchyErrorMessage(err)).toBe('대상을 찾을 수 없습니다')
  })

  it('axios 에러가 아니면 알 수 없는 오류로 폴백한다', () => {
    expect(extractHierarchyErrorMessage(new Error('boom'))).toBe('알 수 없는 오류가 발생했습니다')
  })
})

describe('canEditHierarchy', () => {
  it('역할 로직 확정 전까지 항상 true를 반환한다 (ADR-0031 대기)', () => {
    expect(canEditHierarchy()).toBe(true)
  })
})
