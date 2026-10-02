// 증빙 화면 순수 로직 — 파일 검증·회차 표기·오류 문구. React·axios 비의존(node 환경 테스트).
import { KIND_LABEL, STATUS_LABEL } from '@/features/schedule/schedule.pure'
import type { CycleItem } from '@/features/schedule/api/useSchedule'
import { ALLOWED_EXTENSIONS, ALLOWED_MIME_TYPES, MAX_FILE_SIZE_BYTES } from './types'

export function validateFile(file: { name: string; size: number; type: string }): string | null {
  if (file.size > MAX_FILE_SIZE_BYTES) {
    return `파일 크기(${(file.size / 1024 / 1024).toFixed(1)}MB)가 50MB를 초과합니다.`
  }
  const ext = '.' + file.name.split('.').pop()?.toLowerCase()
  const mimeOk = (ALLOWED_MIME_TYPES as readonly string[]).includes(file.type)
  const extOk = ALLOWED_EXTENSIONS.includes(ext)
  if (!mimeOk && !extOk) {
    return `허용되지 않는 파일 형식입니다. (${ALLOWED_EXTENSIONS.join(', ')})`
  }
  return null
}

export function cycleLabel(cycle: Pick<CycleItem, 'name' | 'kind' | 'status'>): string {
  const kind = KIND_LABEL[cycle.kind] ?? cycle.kind
  const status = STATUS_LABEL[cycle.status] ?? cycle.status
  return `${cycle.name} · ${kind} · ${status}`
}

/** 진행 중 회차를 앞에 둔다 — 업로드 대상은 대부분 진행 중 회차다. 같은 상태 안에서는 서버 순서 유지. */
export function sortCyclesForUpload<T extends Pick<CycleItem, 'status'>>(cycles: T[]): T[] {
  return [...cycles.filter((c) => c.status === 'open'), ...cycles.filter((c) => c.status !== 'open')]
}

/** 마감·승인 회차는 내부회계관리자만 편집할 수 있다(ADR-0032 §2.5) — 선택은 허용하고 안내만 한다. */
export function closedCycleNotice(cycle: Pick<CycleItem, 'status'> | undefined): string | null {
  if (!cycle || cycle.status === 'open') return null
  return '마감된 회차입니다. 내부회계관리자만 증빙을 올릴 수 있습니다.'
}

interface ErrorLike {
  response?: { status?: number; data?: { detail?: unknown } }
}

/**
 * 업로드·삭제 오류 문구. 권한·회차 판정(403/404/409/422)은 서버 문구가 사유를 담고 있어 그대로 보여준다
 * — "업로드 중 오류"로 뭉개면 통제책임자가 아닌지, 회차가 마감됐는지 알 수 없다.
 */
export function resolveEvidenceError(error: unknown, fallback = '업로드 중 오류가 발생했습니다.'): string {
  const res = (error as ErrorLike | null)?.response
  const status = res?.status
  if (status === 413) return '파일 크기가 서버 허용 한도를 초과했습니다.'
  if (status === 415) return '허용되지 않는 파일 형식입니다.'
  const detail = res?.data?.detail
  if (typeof detail === 'string' && detail) return detail
  return fallback
}
