/**
 * 업로드 마법사 순수 로직 (8-D2) — 폼 구성·요약. DOM·네트워크 없음(`upload.test.ts`).
 */
import type { AccountNode, UploadResponse, UploadSheetCandidate } from './types'

export type UploadMode = 'upload' | 'attach'

export interface UploadParams {
  mode: 'preview' | 'commit'
  sheet?: string | null
  unit?: number | null
  basis?: string | null
  includePrior?: boolean
  finalize?: boolean
  mapping?: Record<string, string> | null
  categoryMap?: Record<string, string> | null
  bridgeColumn?: string | null
}

/** 업로드/결합 폼 필드 — 빈 값은 보내지 않는다(서버 기본값을 쓴다). 파일은 호출자가 붙인다. */
export function formFields(uploadMode: UploadMode, p: UploadParams): [string, string][] {
  const out: [string, string][] = [['mode', p.mode]]
  if (p.sheet) out.push(['sheet', p.sheet])
  if (p.unit) out.push(['unit', String(p.unit)])
  if (p.basis) out.push(['basis', p.basis])
  if (p.finalize === false) out.push(['finalize', 'false'])
  if (uploadMode === 'upload') {
    if (p.includePrior) out.push(['include_prior', 'true'])
    if (p.mapping) out.push(['mapping', JSON.stringify(p.mapping)])
  } else {
    if (p.bridgeColumn) out.push(['bridge_column', p.bridgeColumn])
    if (p.categoryMap && Object.keys(p.categoryMap).length) out.push(['category_map', JSON.stringify(p.categoryMap)])
  }
  return out
}

/** 시트 종류로 기본 방식을 정한다 — 정산표(가로 연도형)는 공시 재무제표에 **결합**이 기본(마스터 확정 D1) */
export const defaultMode = (c: UploadSheetCandidate | undefined): UploadMode =>
  c?.kind === 'horizontal_years' ? 'attach' : 'upload'

/** 제안 대응 요약 — 기존 계정에 붙는 행 / 새로 만드는 행 */
export function mappingCounts(suggested: Record<string, string>): { existing: number; created: number } {
  const vals = Object.values(suggested)
  const created = vals.filter((v) => v === 'new').length
  return { existing: vals.length - created, created }
}

/** 업로드 preview 요약 — 계정 행 수·제외 행·임시계정 예정(원본 소계 불일치) 건수 */
export function uploadSummary(r: UploadResponse) {
  const accounts = r.rows.filter((x) => x.kind !== 'section_header' && !x.excluded).length
  const excluded = r.rows.filter((x) => x.excluded).map((x) => x.label)
  const suspense = r.statements.reduce((n, s) => n + s.suspense.length, 0)
  return { accounts, excluded, suspense, diffs: r.subtotal_diffs.length }
}

/** 결합 대응표 후보 — 공시 계정 이름(트리 전체, 중복 제거·순서 유지) */
export function accountNames(nodes: AccountNode[], out: string[] = []): string[] {
  for (const n of nodes) {
    if (!out.includes(n.name)) out.push(n.name)
    accountNames(n.children, out)
  }
  return out
}

/** 대응표가 매핑 실패 값을 모두 채웠는가 */
export const categoryMapComplete = (unmatched: string[], map: Record<string, string>) =>
  unmatched.every((v) => Boolean(map[v]))
