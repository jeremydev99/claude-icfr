import { describe, expect, it } from 'vitest'
import {
  closedCycleNotice,
  cycleLabel,
  resolveEvidenceError,
  sortCyclesForUpload,
  validateFile,
} from './evidence.pure'

describe('validateFile', () => {
  it('허용 형식·용량이면 null', () => {
    expect(validateFile({ name: 'a.pdf', size: 1024, type: 'application/pdf' })).toBeNull()
  })
  it('50MB 초과는 거부', () => {
    expect(validateFile({ name: 'a.pdf', size: 51 * 1024 * 1024, type: 'application/pdf' })).toMatch('50MB')
  })
  it('MIME 이 비어도 확장자가 허용이면 통과(hwp)', () => {
    expect(validateFile({ name: '보고.HWP', size: 10, type: '' })).toBeNull()
  })
  it('형식·확장자 모두 밖이면 거부', () => {
    expect(validateFile({ name: 'a.exe', size: 10, type: 'application/x-msdownload' })).toMatch('허용되지 않는')
  })
})

describe('cycleLabel', () => {
  it('회차명·종류·상태를 한국어로', () => {
    expect(cycleLabel({ name: '2026 1분기', kind: 'operation', status: 'open' })).toBe('2026 1분기 · 운영평가 · 진행 중')
  })
  it('모르는 값은 원문 그대로', () => {
    expect(cycleLabel({ name: 'X', kind: 'etc', status: 'zzz' })).toBe('X · etc · zzz')
  })
})

describe('sortCyclesForUpload', () => {
  it('진행 중을 앞으로, 상태 내 순서는 유지', () => {
    const cs = [
      { id: '1', status: 'closed' },
      { id: '2', status: 'open' },
      { id: '3', status: 'approved' },
      { id: '4', status: 'open' },
    ]
    expect(sortCyclesForUpload(cs).map((c) => c.id)).toEqual(['2', '4', '1', '3'])
  })
})

describe('closedCycleNotice', () => {
  it('진행 중·미선택이면 안내 없음', () => {
    expect(closedCycleNotice({ status: 'open' })).toBeNull()
    expect(closedCycleNotice(undefined)).toBeNull()
  })
  it('마감·승인이면 관리자 전용 안내', () => {
    expect(closedCycleNotice({ status: 'closed' })).toMatch('내부회계관리자')
    expect(closedCycleNotice({ status: 'approved' })).toMatch('내부회계관리자')
  })
})

describe('resolveEvidenceError', () => {
  const err = (status: number, detail?: unknown) => ({ response: { status, data: { detail } } })
  it('413·415 는 고정 문구', () => {
    expect(resolveEvidenceError(err(413))).toMatch('한도')
    expect(resolveEvidenceError(err(415))).toMatch('형식')
  })
  it('403 은 서버 사유를 그대로', () => {
    expect(resolveEvidenceError(err(403, '이 통제의 통제책임자만 증빙을 편집할 수 있습니다')))
      .toBe('이 통제의 통제책임자만 증빙을 편집할 수 있습니다')
  })
  it('422 처럼 detail 이 배열이면 기본 문구', () => {
    expect(resolveEvidenceError(err(422, [{ msg: 'x' }]))).toBe('업로드 중 오류가 발생했습니다.')
  })
  it('응답 없음(네트워크)·지정 기본 문구', () => {
    expect(resolveEvidenceError(new Error('net'), '삭제 실패')).toBe('삭제 실패')
    expect(resolveEvidenceError(null)).toBe('업로드 중 오류가 발생했습니다.')
  })
})
