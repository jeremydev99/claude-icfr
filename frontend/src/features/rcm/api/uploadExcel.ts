import apiClient from '@/lib/axios'
import type { RcmDiff } from '../year/RcmDiffView'

// Exact types from backend/app/api/rcm.py upload_excel endpoint

export interface ExcelUploadSummary {
  total_rows: number    // len(parsed.controls) + len(parsed.errors)
  valid_rows: number    // len(parsed.controls) — successfully parsed
  errors: string[]      // e.g. ["Row 8: 통제활동번호(G) 누락"]
  warnings: string[]    // e.g. ["Row 10: 위험평가 'XX' 무효 → LR 사용"]
}

export interface ExcelPreviewItem {
  code: string
  name: string
  description: string | null
  objective: string | null
  owner_name: string | null
  risk_code: string
  is_key_control: boolean
  preventive_detective: string
  auto_manual: string
  activity_approval: boolean
  activity_verification: boolean
  activity_physical: boolean
  activity_master_data: boolean
  activity_reconciliation: boolean
  activity_supervision: boolean
  assertions: string[]
  related_accounts: string | null
  frequency: string
  ipe_relevant: string
  related_systems: string | null
  euc_description: string | null
}

// 정상 미리보기 응답 (status 필드 없음)
/** 현재 RCM 대비 차이 (2026-10-08) — 엑셀에 없는 기존 항목은 지우지 않고 missing 으로만 알린다. */
export interface ExcelSyncPreview {
  diff: RcmDiff
  summary_text: string
  missing: Record<string, string[]>
  missing_count: number
  warnings: string[]       // 반영하지 않는 것 (상위 변경·모르는 어서션)
  op_count: number         // 0 이면 바꿀 것이 없다
}

export interface ExcelPreviewSuccess {
  summary: ExcelUploadSummary
  preview: ExcelPreviewItem[]  // max 20 items (valid rows only)
  sync: ExcelSyncPreview
}

// 헤더 탐색 범위 확장 필요 응답
export interface ExcelPreviewNeedsExpansion {
  status: 'needs_expansion'
  message: string
  current_range: number
  next_range: number
  expand_param: string    // 힌트 문자열 — 무시하고 next_range만 사용
  sheets_checked: string[]
}

export type ExcelPreviewResponse = ExcelPreviewSuccess | ExcelPreviewNeedsExpansion

export function isNeedsExpansion(
  res: ExcelPreviewResponse
): res is ExcelPreviewNeedsExpansion {
  return (res as ExcelPreviewNeedsExpansion).status === 'needs_expansion'
}

export interface ExcelCreatedCounts {
  processes: number
  sub_processes: number
  risks: number
  controls: number
  assertions: number
}

export interface ExcelCommitResponse {
  summary: ExcelUploadSummary
  created: ExcelCreatedCounts
  updated: Omit<ExcelCreatedCounts, 'assertions'>
  summary_text: string
  missing_count: number
  warnings: string[]
}

const UPLOAD_URL = '/api/rcm/upload-excel'

export async function previewExcel(
  file: File,
  expandTo?: number
): Promise<ExcelPreviewResponse> {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('mode', 'preview')
  if (expandTo !== undefined) {
    formData.append('expand_to', String(expandTo))
  }
  // Do NOT set Content-Type manually — browser sets multipart boundary automatically
  const res = await apiClient.post<ExcelPreviewResponse>(UPLOAD_URL, formData)
  return res.data
}

export async function commitExcel(
  file: File,
  expandTo?: number
): Promise<ExcelCommitResponse> {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('mode', 'commit')
  if (expandTo !== undefined) {
    formData.append('expand_to', String(expandTo))
  }
  const res = await apiClient.post<ExcelCommitResponse>(UPLOAD_URL, formData)
  return res.data
}
