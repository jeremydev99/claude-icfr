/** 거버넌스 표시용 순수 함수 — `governance.test.ts`. 규칙 판정은 하지 않는다(서버 `can`). */
import type { GovernanceInfo, ReviewPath } from './types'

export const EVENT_LABELS: Record<string, string> = {
  item_confirm: '항목 확인',
  item_unconfirm: '확인 취소',
  value_change: '값 변경',
  submit_review: '검토 요청',
  withdraw: '요청 회수',
  review_done: '책임관리자 검토 완료',
  review_return: '반려',
  approve: '승인(확정)',
  external_approve: '외부 승인 기록',
  reopen_request: '재오픈 요청',
  reopen_approve: '재오픈 승인',
  reopen_reject: '재오픈 거절',
}

export const BODY_LABELS: Record<string, string> = { ceo: '대표이사', board: '이사회' }

export type StepState = 'done' | 'current' | 'todo' | 'skip'
export interface Step { key: string; label: string; who: string | null; state: StepState }

/** 결재선 — 경로별 단계와 진행 상태. 작성 → (책임 검토) → 마스터 승인 | 대표이사·이사회 승인 */
export function approvalSteps(status: string, g: GovernanceInfo, defaultPath: ReviewPath = 'master'): Step[] {
  const path = g.review_path ?? g.preview_path ?? defaultPath
  const submitted = status !== 'draft'
  const confirmed = status === 'confirmed'
  const steps: Step[] = [{ key: 'submit', label: '작성·검토 요청', who: g.requested_by?.name ?? null,
    state: submitted ? 'done' : 'current' }]
  if (path === 'lead_then_master') {
    steps.push({ key: 'review', label: '책임관리자 검토', who: g.reviewed_by?.name ?? null,
      state: g.reviewed_by ? 'done' : submitted && !confirmed ? 'current' : confirmed ? 'done' : 'todo' })
  }
  if (path === 'external') {
    const ext = g.external_approvals.filter((e) => e.purpose === 'approve').at(-1)
    steps.push({ key: 'approve', label: '대표이사·이사회 승인', who: ext ? BODY_LABELS[ext.approver_body] : null,
      state: confirmed ? 'done' : submitted ? 'current' : 'todo' })
  } else {
    const waitingReview = path === 'lead_then_master' && !g.reviewed_by
    steps.push({ key: 'approve', label: '마스터관리자 승인', who: g.confirmed_by?.name ?? null,
      state: confirmed ? 'done' : submitted && !waitingReview ? 'current' : 'todo' })
  }
  return steps
}

/** 이벤트 값 한 줄 — {"질적 판단 근거": "새 근거"} → "질적 판단 근거: 새 근거". 긴 값은 줄인다 */
export function formatValues(v: Record<string, unknown> | null | undefined, max = 80): string {
  if (!v) return ''
  return Object.entries(v).map(([k, x]) => {
    const s = x === null || x === undefined ? '—' : typeof x === 'object' ? JSON.stringify(x) : String(x)
    return `${k}: ${s.length > max ? s.slice(0, max) + '…' : s}`
  }).join(' · ')
}
