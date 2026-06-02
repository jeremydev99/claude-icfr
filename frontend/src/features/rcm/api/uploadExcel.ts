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

export interface ExcelPreviewResponse {
  summary: ExcelUploadSummary
  preview: ExcelPreviewItem[]  // max 20 items (valid rows only)
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

export async function previewExcel(file: File): Promise<ExcelPreviewResponse> {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('mode', 'preview')
  // Do NOT set Content-Type manually — browser sets multipart boundary automatically
  const res = await proxyClient.post<ExcelPreviewResponse>(UPLOAD_URL, formData)
  return res.data
}

export async function commitExcel(file: File): Promise<ExcelCommitResponse> {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('mode', 'commit')
  const res = await proxyClient.post<ExcelCommitResponse>(UPLOAD_URL, formData)
  return res.data
}

