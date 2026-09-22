// EUC·IUC 도메인 타입 (5-1). 백엔드 `schemas/euc.py` 와 1:1.
//
// **선택지 값 목록을 여기 두지 않는다** — `GET /api/euc/meta` 가 준다. 화면이 목록을 따로 들면
// 백엔드 상수와 어긋나고, 0건인 값이 선택지·집계에서 사라진다(ClaudeICFR.md 13.9-40).

export interface Option {
  value: string
  label: string
}

export interface EucMeta {
  complexity: Option[]
  /** EUC 전용 — RCM 수행주기와 값 집합이 다르다(E·S·건별이 있다) */
  change_frequency: Option[]
  risk_grade: Option[]
  importance: Option[]
  info_type: Option[]
  identification_threshold: string
}

export interface EucControlRef {
  id: string
  code: string
  name: string
}

export interface EucFile {
  id: string
  name: string
  description: string | null
  has_macro: boolean | null
  /** null = 미평가 */
  complexity: string | null
  change_frequency: string | null
  storage_path: string | null
  managing_department: string | null
  manager_name: string | null
  /** 원천 양식에 적혀 있던 위험평가 — 참고값. 산출 등급과 섞지 않는다 */
  source_risk_rating: string | null
  source_risk_basis: string | null
  // ── 산출값 (서버가 계산, 저장하지 않는다) ──
  importance: string | null
  risk_grade: string | null
  identified: boolean | null
  /** 원천 참고값과 산출 등급이 둘 다 있는데 다르면 true — 검토 신호 */
  source_mismatch: boolean
  /** 참조하는 살아 있는 통제. 비어 있으면 "참조 통제 0건" */
  controls: EucControlRef[]
  can_edit: boolean
  created_at: string
  updated_at: string
}

export interface EucFileList {
  items: EucFile[]
  total: number
  can_create: boolean
}

export type EucFilePayload = Partial<
  Pick<EucFile, 'name' | 'description' | 'has_macro' | 'complexity' | 'change_frequency'
    | 'storage_path' | 'managing_department' | 'manager_name'>
>

export interface InfoItem {
  id: string
  control_id: string
  control_code: string | null
  control_name: string | null
  process_code: string | null
  name: string
  info_type: string
  importance: string | null
  euc_file_id: string | null
  euc_file_name: string | null
  system_name: string | null
  itgc_in_scope: string | null
  source_data: string | null
  report_logic: string | null
  input_parameter: string | null
  source_data_review: string | null
  report_logic_control: string | null
  input_parameter_review: string | null
  design_assessment_result: string | null
  can_edit: boolean
}

export interface InfoItemList {
  items: InfoItem[]
  total: number
  /** 정보 항목을 새로 붙일 수 있는 통제 — 통제 선택지를 이것으로 좁힌다 */
  writable_control_ids: string[]
}

export type InfoItemPayload = Partial<Omit<InfoItem,
  'id' | 'control_code' | 'control_name' | 'process_code' | 'euc_file_name' | 'can_edit'>>

export interface CountBucket {
  value: string
  label: string
  count: number
}

export interface EucIucSummary {
  file_total: number
  item_total: number
  identified: number
  unevaluated: number
  unreferenced_files: number
  source_mismatch: number
  identification_threshold: string
  risk_grade: CountBucket[]
  importance: CountBucket[]
  info_type: CountBucket[]
}
