// 대시보드 집계 응답 (4-1). 백엔드 `GET /api/rcm/summary` 와 1:1.
//
// **라벨을 백엔드가 준다.** 프로세스명처럼 백엔드에만 있는 값이 섞여 있어 매핑을
// 프론트에 두면 절반만 번역된다. 화면은 받은 label 을 그대로 그린다.

export interface SummaryBucket {
  /** RCM 검색에 그대로 넘기는 필터 값 */
  value: string
  label: string
  count: number
}

export interface SummaryGroup {
  key: string
  label: string
  /** null 이면 드릴스루 불가 — 현재 모든 묶음에 값이 있다 */
  filter_param: string | null
  buckets: SummaryBucket[]
}

export interface OrgSummary {
  unassigned: number
  buckets: SummaryBucket[]
}

export interface ProgressSummary {
  cycles: number
  targets: number
  activities: number
  completed: number
  incomplete: number
}

export interface RcmSummary {
  control_total: number
  process_total: number
  groups: SummaryGroup[]
  org: OrgSummary
  progress: ProgressSummary
}
