// 내 평가(2026-10-15) — 화면 판정 순수 함수. 최종 판정은 서버(api/assessment.py)다.
import type { ActivityRead, SampleRead, WorklistRow } from './types'

export const KIND_LABEL: Record<string, string> = { design: '설계평가', operation: '운영평가' }

export const STATE_LABEL: Record<WorklistRow['state'], string> = {
  not_started: '미착수',
  draft: '작성 중',
  submitted: '승인 대기',
  approved: '승인 완료',
}

export const STATE_VARIANT: Record<WorklistRow['state'], 'outline' | 'secondary' | 'default'> = {
  not_started: 'outline',
  draft: 'secondary',
  submitted: 'secondary',
  approved: 'default',
}

export const RESULT_LABEL: Record<string, string> = { pass: '적정', fail: '미흡', na: '해당 없음' }

export const METHODS = [
  { value: 'inquiry', label: '질문' },
  { value: 'observation', label: '관찰' },
  { value: 'inspection', label: '문서검사' },
  { value: 'reperformance', label: '재수행' },
] as const

export const ROLE_LABEL: Record<string, string> = {
  control_owner: '통제책임자',
  assessor: '평가자',
  dept_approver: '부서승인자',
}

export const STAGE_LABEL: Record<string, string> = { dept: '부서승인', assessor: '평가자 승인' }

export const FREQ_LABEL: Record<string, string> = { O: '수시', D: '일', W: '주', M: '월', Q: '분기', A: '연' }

export function methodsToList(v: string | null | undefined): string[] {
  return (v ?? '').split(',').map((s) => s.trim()).filter(Boolean)
}

/** 체크 순서와 무관하게 원천 순서(질문·관찰·문서검사·재수행)로 — 서버 비교가 흔들리지 않게 */
export function listToMethods(list: string[]): string | null {
  const order = METHODS.map((m) => m.value as string)
  const out = order.filter((m) => list.includes(m))
  return out.length ? out.join(',') : null
}

export function methodsLabel(v: string | null | undefined): string {
  const list = methodsToList(v)
  return list.length ? list.map((m) => METHODS.find((x) => x.value === m)?.label ?? m).join(', ') : '-'
}

/** 제출 조건을 채운 샘플 — 서버 `_sample_done` 과 같은 규칙(식별·결과·증빙) */
export function sampleDone(s: SampleRead): boolean {
  return Boolean((s.label ?? '').trim()) && s.result !== null && s.evidence.length > 0
}

/** 샘플에서 빠진 것 — 화면 안내용 */
export function sampleMissing(s: SampleRead): string[] {
  const out: string[] = []
  if (!(s.label ?? '').trim()) out.push('샘플 식별')
  if (s.result === null) out.push('결과')
  if (s.evidence.length === 0) out.push('증빙')
  return out
}

/** 제출 가능 여부와 막는 이유 — 필요 수 미달·빈 줄·결론 없음. 적게 제출은 불가(마스터 결정) */
export function submitBlockers(activity: Pick<ActivityRead, 'result' | 'samples'>, required: number): string[] {
  const done = activity.samples.filter(sampleDone).length
  const out: string[] = []
  if (done < required) out.push(`필요 샘플 ${required}건 중 ${done}건 완료`)
  const partial = activity.samples.filter((s) => !sampleDone(s)).map((s) => s.seq)
  if (done >= required && partial.length) out.push(`샘플 ${partial.join(', ')}번이 비어 있음 — 채우거나 줄을 지우세요`)
  if (!activity.result || !RESULT_LABEL[activity.result]) out.push('테스트 결론 미선택')
  return out
}

/** 줄 삭제 가능 — 필요 수 아래로는 줄일 수 없다 */
export function canDeleteSample(sampleCount: number, required: number): boolean {
  return sampleCount > required
}

/** 목록 상단 집계 — 상태별 건수와 필요 샘플 합계 */
export function summarize(rows: WorklistRow[]) {
  const by: Record<WorklistRow['state'], number> = { not_started: 0, draft: 0, submitted: 0, approved: 0 }
  let samples = 0
  for (const r of rows) {
    by[r.state] += 1
    samples += r.required_samples
  }
  return { total: rows.length, by, samples, unassigned: rows.filter((r) => !r.owner_id).length }
}

export type RoleFilter = 'all' | 'write' | 'approve'

export const ROLE_FILTER_LABEL: Record<RoleFilter, string> = {
  write: '작성할 통제',
  approve: '승인할 통제',
  all: '전체',
}

/**
 * 작성할 것 = 내가 통제책임자. 승인할 것 = **지금 내가 승인할 수 있는 제출 건**(서버 `can_approve`, 2026-10-16 조사 1) —
 * 역할만 가진 미착수·작성 중·승인 완료 건과, 직무분리로 막힌 본인 작성 건은 세지 않는다. 역할 기준 목록은 '전체'에서 본다.
 */
export function matchesRole(r: Pick<WorklistRow, 'my_roles' | 'can_approve'>, f: RoleFilter): boolean {
  if (f === 'write') return r.my_roles.includes('control_owner')
  if (f === 'approve') return r.can_approve.length > 0
  return true
}

export const OWNER_ALL = '__all__'
export const OWNER_NONE = '__none__'

/** 전체 보기의 통제책임자 고르기 — 미배정은 OWNER_NONE */
export function matchesOwner(r: Pick<WorklistRow, 'owner_id'>, owner: string): boolean {
  if (owner === OWNER_ALL) return true
  if (owner === OWNER_NONE) return !r.owner_id
  return r.owner_id === owner
}

/** 통제책임자 선택지 — 이름순, 건수 포함 */
export function ownerOptions(rows: Pick<WorklistRow, 'owner_id' | 'owner_name'>[]) {
  const m = new Map<string, { id: string; name: string; count: number }>()
  for (const r of rows) {
    if (!r.owner_id) continue
    const o = m.get(r.owner_id) ?? { id: r.owner_id, name: r.owner_name ?? '(이름 없음)', count: 0 }
    o.count += 1
    m.set(r.owner_id, o)
  }
  return [...m.values()].sort((a, b) => a.name.localeCompare(b.name, 'ko'))
}

/** 캡처 붙여넣기 이름인가 — 브라우저는 클립보드 이미지에 `image.png` 같은 고정 이름을 붙인다 */
export function isClipboardName(name: string): boolean {
  return !name.trim() || /^image\.(png|jpe?g|gif|bmp|webp)$/i.test(name.trim())
}

/**
 * 붙여넣은 캡처의 파일명(2026-10-16, 조사 2) — 모두 `image.png` 가 되면 증빙을 구분할 수 없다.
 * `{통제코드}_S{샘플번호}_{yyyyMMdd-HHmmss}[_n].{확장자}`. 탐색기에서 복사한 실제 파일은 이름을 그대로 둔다.
 */
export function pastedFileName(original: string, type: string, controlCode: string | null, seq: number,
                               now: Date, index = 0): string {
  if (!isClipboardName(original)) return original
  const ext = (original.split('.').pop() || type.split('/').pop() || 'png').toLowerCase().replace('jpeg', 'jpg')
  const p = (n: number) => String(n).padStart(2, '0')
  const stamp = `${now.getFullYear()}${p(now.getMonth() + 1)}${p(now.getDate())}-${p(now.getHours())}${p(now.getMinutes())}${p(now.getSeconds())}`
  const code = (controlCode ?? '').replace(/[\\/:*?"<>|\s]+/g, '-') || '증빙'
  return `${code}_S${seq}_${stamp}${index ? `_${index + 1}` : ''}.${ext}`
}

export function progressText(r: Pick<WorklistRow, 'samples_done' | 'required_samples' | 'state'>): string {
  if (r.state === 'not_started') return `0/${r.required_samples}`
  return `${Math.min(r.samples_done, r.required_samples)}/${r.required_samples}`
}

/**
 * 기본 회차(2026-10-16 점검) — 진행 중이면서 **내 담당이 있는** 회차를 먼저. 없으면 진행 중, 없으면 첫 회차.
 * 회차가 여럿일 때 내 담당이 없는 회차로 열려 "맡은 통제가 없습니다"로 시작하던 것.
 */
export function pickDefaultCycle(cycles: { id: string; status: string }[],
                                 myCounts: Record<string, number | undefined>): string | null {
  const open = cycles.filter((c) => c.status === 'open')
  return (open.find((c) => (myCounts[c.id] ?? 0) > 0) ?? open[0] ?? cycles[0])?.id ?? null
}
