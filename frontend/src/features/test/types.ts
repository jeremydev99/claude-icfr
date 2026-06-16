export type TestRunStatus = 'planned' | 'in_progress' | 'completed' | 'approved'
export type TestResult = 'pass' | 'fail' | 'n/a'

export interface TestRun {
  id: string
  control_id: string
  fiscal_year: number
  status: TestRunStatus
  tester_id: string | null
  test_date: string | null
  result: TestResult | null
  notes: string | null
  wtt_summary: string | null
  existing_process_notes: string | null
  method_inquiry: boolean
  method_observation: boolean
  method_inspection: boolean
  method_reperformance: boolean
  population: string | null
  test_frequency: 'O' | 'D' | 'W' | 'M' | 'Q' | 'A' | null
  sample_size: number | null
  procedure: string | null
  approved_by_id: string | null
  approved_at: string | null
  created_at: string
  updated_at: string
}

export interface TestRunCreatePayload {
  control_id: string
  fiscal_year: number
}

export interface TestRunListResponse {
  items: TestRun[]
  total: number
  skip: number
  limit: number
}

export interface TestRunSearchParams {
  fiscal_year?: number
  status_filter?: TestRunStatus
  skip?: number
  limit?: number
}

export const STATUS_LABELS: Record<TestRunStatus, string> = {
  planned: '계획',
  in_progress: '진행중',
  completed: '완료',
  approved: '승인',
}

export const STATUS_BADGE_CLASS: Record<TestRunStatus, string> = {
  planned: 'bg-gray-100 text-gray-700 border-gray-200',
  in_progress: 'bg-blue-100 text-blue-700 border-blue-200',
  completed: 'bg-green-100 text-green-700 border-green-200',
  approved: 'bg-purple-100 text-purple-700 border-purple-200',
}

export const RESULT_LABELS: Record<TestResult, string> = {
  pass: '적합',
  fail: '부적합',
  'n/a': '해당없음',
}

export const RESULT_BADGE_CLASS: Record<TestResult, string> = {
  pass: 'bg-green-100 text-green-700 border-green-200',
  fail: 'bg-red-100 text-red-700 border-red-200',
  'n/a': 'bg-gray-100 text-gray-500 border-gray-200',
}

export interface TestStep {
  id: string
  test_run_id: string
  step_order: number
  description: string
  result: 'pass' | 'fail'
  created_at: string
}

export interface TestStepCreatePayload {
  test_run_id: string
  step_order: number
  description: string
  result: 'pass' | 'fail'
}

export interface TestStepUpdatePayload {
  description?: string
  result?: 'pass' | 'fail'
}

export interface TestRunUpdatePayload {
  test_date?: string | null
  result?: TestResult | null
  sample_size?: number | null
  method_inspection?: boolean | null
  method_reperformance?: boolean | null
  method_observation?: boolean | null
  method_inquiry?: boolean | null
}

export interface UserBrief {
  id: string
  display_name: string
}

export interface TransitionRequest {
  to_status: 'in_progress' | 'completed' | 'approved'
  reason?: string
}

export interface TestStatusHistory {
  id: string
  test_run_id: string
  from_status: TestRunStatus | null
  to_status: TestRunStatus
  changed_by: UserBrief
  changed_by_id: string
  changed_at: string
  reason: string | null
}
