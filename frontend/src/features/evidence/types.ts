export interface EvidenceFile {
  id: string
  filename: string
  mime_type: string
  size_bytes: number
  minio_key: string | null
  sha256: string | null
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
}

export interface EvidenceLinkSearchParams {
  file_id?: string
  skip?: number
  limit?: number
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
