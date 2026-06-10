import axios from 'axios'

// Separate instance with relative baseURL so Vite proxy handles /api → localhost:8000
// (apiClient uses http://localhost:8000 directly and may hit CORS on multipart requests)
const proxyClient = axios.create({ baseURL: '' })
proxyClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

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
export interface ExcelPreviewSuccess {
  summary: ExcelUploadSummary
  preview: ExcelPreviewItem[]  // max 20 items (valid rows only)
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
  const res = await proxyClient.post<ExcelPreviewResponse>(UPLOAD_URL, formData)
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
  const res = await proxyClient.post<ExcelCommitResponse>(UPLOAD_URL, formData)
  return res.data
}
