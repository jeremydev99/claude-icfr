// 내 평가 — 서버 계약(backend/app/schemas/assessment.py)과 1:1
export interface WorklistRow {
  control_id: string
  control_code: string | null
  control_name: string | null
  process_code: string | null
  frequency: string | null
  auto_manual: string | null
  owner_id: string | null
  owner_name: string | null
  my_roles: string[]
  activity_kind: 'design' | 'test'
  required_samples: number
  sample_basis: string
  rcm_test_methods: string | null
  rcm_population: string | null
  rcm_test_procedure: string | null
  state: 'not_started' | 'draft' | 'submitted' | 'approved'
  activity_id: string | null
  activity_count: number
  samples_done: number
  evidence_count: number
  pending_stages: string[]
  can_approve: string[]
}

export interface SampleEvidence {
  link_id: string
  file_id: string
  filename: string
  title: string | null
}

export interface SampleRead {
  id: string
  activity_id: string
  seq: number
  label: string | null
  sampled_on: string | null
  result: string | null
  note: string | null
  evidence: SampleEvidence[]
}

export interface ApprovalRead {
  id: string
  activity_id: string
  stage: string
  approved_by_name: string | null
  approved_at: string
  note: string | null
}

export interface ActivityRead {
  id: string
  cycle_id: string
  control_id: string
  activity_kind: string
  result: string | null
  note: string | null
  performed_by_id: string
  performed_by_name: string | null
  performed_at: string
  status: 'draft' | 'submitted'
  submitted_at: string | null
  required_samples: number | null
  test_methods: string | null
  population: string | null
  procedure: string | null
  samples: SampleRead[]
  approvals: ApprovalRead[]
}

export type ActivityPatch = Partial<Pick<ActivityRead, 'result' | 'note' | 'test_methods' | 'population' | 'procedure'>>
export type SamplePatch = Partial<Pick<SampleRead, 'label' | 'sampled_on' | 'result' | 'note'>>
