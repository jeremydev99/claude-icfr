export interface EvidenceFile {
  id: string
  filename: string
  mime_type: string
  size_bytes: number
  minio_key: string | null
  sha256: string | null
  // 부착 대상 — 통제 × 회차 (ADR-0032 §2.7). 기존 증빙(회차 도입 전)은 null.
  cycle_id: string | null
  control_id: string | null
  uploaded_by_id: string
  created_at: string
  updated_at: string
}

export interface EvidenceLink {
  id: string
  file_id: string
  linked_entity_type: string
  linked_entity_id: string
  created_at: string
}

export interface EvidenceFileListResponse {
  items: EvidenceFile[]
  total: number
  skip: number
  limit: number
}

export interface EvidenceFileSearchParams {
  skip?: number
  limit?: number
  cycle_id?: string
  control_id?: string
}

export interface EvidenceLinkSearchParams {
  file_id?: string
  skip?: number
  limit?: number
}

export interface EvidenceUploadPayload {
  file: File
  cycleId: string
  controlId: string
}

export interface CycleTarget {
  control_id: string
  control_code: string | null
}

export const MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024 // 50MB

export const ALLOWED_MIME_TYPES = [
  'application/pdf',
  'image/png',
  'image/jpeg',
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  'application/x-hwp',
  'application/haansofthwp',
  'application/vnd.hancom.hwp',
] as const

export const ALLOWED_EXTENSIONS = ['.pdf', '.png', '.jpg', '.jpeg', '.xlsx', '.docx', '.hwp']
