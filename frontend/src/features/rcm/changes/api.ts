import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import apiClient from '@/lib/axios'
import { useActiveTenantId } from '@/features/auth/store'

export interface ControlChange {
  id: string
  control_id: string
  control_code: string | null
  control_name: string | null
  changes: Record<string, unknown>
  before: Record<string, unknown>
  note: string | null
  status: 'draft' | 'dept_review' | 'dept_approved' | 'in_batch' | 'applied' | 'rejected' | 'withdrawn'
  status_label: string
  author: string | null
  is_mine: boolean
  submitted_at: string | null
  dept_approver: string | null
  dept_skipped: string | null
  dept_note: string | null
  batch_id: string | null
  admin_decided_by: string | null
  admin_note: string | null
  rejected_by: 'dept' | 'admin' | null
  updated_at: string
  can_dept_decide: boolean
}

export interface ChangeBatch {
  id: string
  status: 'review' | 'done'
  submitted_by: string | null
  created_at: string
  note: string | null
  item_count: number
  decided_by: string | null
  decided_at: string | null
  result: { applied: number; rejected: number } | null
  can_decide: boolean
  items: ControlChange[]
}

export interface Overview {
  mine: ControlChange[]
  dept: ControlChange[]
  queue: ControlChange[]
  batches: ChangeBatch[]
  can: { batch_submit: boolean; direct_edit: boolean }
}

const key = (tid: string | null, ...r: unknown[]) => ['tenant', tid ?? 'no-tenant', 'rcm-changes', ...r]

export function useChangeOverview() {
  const tid = useActiveTenantId()
  return useQuery({ queryKey: key(tid, 'overview'), queryFn: async () => (await apiClient.get<Overview>('/api/rcm-changes')).data })
}

export function useControlChange(controlId: string | undefined) {
  const tid = useActiveTenantId()
  return useQuery({
    queryKey: key(tid, 'control', controlId),
    enabled: !!controlId,
    queryFn: async () => (await apiClient.get<{ change: ControlChange | null; direct_edit: boolean }>(`/api/rcm-changes/control/${controlId}`)).data,
  })
}

/** 변경 결재 쓰기 — 끝나면 이 기능의 목록·통제 목록을 다시 읽는다 */
export function useChangeAction() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({ method, url, body }: { method: 'post' | 'put'; url: string; body?: unknown }) =>
      (await apiClient.request({ method, url, data: body })).data,
    onSuccess: () => {
      void qc.invalidateQueries({ predicate: (q) => JSON.stringify(q.queryKey).includes('rcm-changes') })
      void qc.invalidateQueries({ predicate: (q) => JSON.stringify(q.queryKey).includes('controls') })
    },
  })
}

export const errText = (e: unknown, f: string) => {
  const d = (e as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
  return typeof d === 'string' ? d : f
}

/** 통제 항목 이름 — 변경 비교 표시용 */
export const FIELD_LABEL: Record<string, string> = {
  name: '통제명', description: '통제 설명', objective: '통제 목적', owner_name: '담당자명', is_key_control: '핵심통제',
  preventive_detective: '예방/적발', auto_manual: '자동/수동', frequency: '수행 빈도', assessment_frequency: '평가 빈도',
  ipe_relevant: 'IPE 관련', activity_approval: '활동: 승인', activity_verification: '활동: 검증', activity_physical: '활동: 물리적 통제',
  activity_master_data: '활동: 기준정보', activity_reconciliation: '활동: 대사', activity_supervision: '활동: 감독',
  related_accounts: '관련 계정', related_systems: '관련 시스템', euc_description: 'EUC 설명',
}

export function showValue(v: unknown): string {
  if (v === null || v === undefined || v === '') return '(없음)'
  if (typeof v === 'boolean') return v ? '예' : '아니오'
  return String(v)
}
