import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import apiClient from '@/lib/axios'
import { useActiveTenantId } from '@/features/auth/store'
import type { PhaseCategory } from '../schedule.pure'

export interface TemplateRow {
  code: string
  name: string
  category: PhaseCategory | 'other'
  start_offset: number
  end_offset: number
  description: string | null
  tasks: string[]
  sort_order?: number
}

export interface PlanItem {
  id: string
  kind: 'standard' | 'custom'
  template_code: string | null
  title: string
  category: PhaseCategory | 'other'
  start_date: string
  end_date: string
  description: string | null
  tasks: string[]
}

export interface PlanResp {
  fiscal_year: number
  plan: null | {
    id: string
    status: 'draft' | 'in_review' | 'approved'
    status_label: string
    version: number
    approval_line: { step: string; label: string }[]
    current_step: number
    approvals: { step: string; user_id: string; name: string; at: string; note: string | null }[]
    requested_by: string | null
    requested_at: string | null
    request_note: string | null
    approved_at: string | null
    returned_reason: string | null
    /** 마지막 승인본의 판 — 없으면 한 번도 승인되지 않음 */
    approved_version: number | null
  }
  /** 작성 중인 판(수정 대상) */
  items: PlanItem[]
  /** 마지막 승인본 — 일정관리 화면(간트·이번 달 할 일)은 이것만 본다. 없으면 표준 일정 */
  approved_items: PlanItem[] | null
  can: { edit: boolean; submit: boolean; approve: boolean; return: boolean; why: Record<string, string> }
  policy_line: string[]
  start_month: number
}

export interface ItemBody {
  kind: 'standard' | 'custom'
  template_code?: string | null
  title?: string | null
  start_date: string
  end_date: string
  description?: string | null
}

const key = (tid: string | null, ...rest: unknown[]) => ['tenant', tid ?? 'no-tenant', 'schedule', ...rest]

export function useTemplates() {
  const tid = useActiveTenantId()
  return useQuery({
    queryKey: key(tid, 'templates'),
    queryFn: async () => (await apiClient.get<{ items: TemplateRow[]; builtin: boolean; categories: string[] }>('/api/schedule/templates')).data,
  })
}

export function usePlan(fy: number) {
  const tid = useActiveTenantId()
  return useQuery({ queryKey: key(tid, 'plan', fy), queryFn: async () => (await apiClient.get<PlanResp>(`/api/schedule/plans/${fy}`)).data })
}

/** 일정안 쓰기 — 응답(갱신된 일정안)을 그대로 캐시에 넣는다 */
export function usePlanAction(fy: number) {
  const tid = useActiveTenantId()
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({ method, path, body }: { method: 'post' | 'put' | 'patch' | 'delete'; path: string; body?: unknown }) =>
      (await apiClient.request<PlanResp>({ method, url: `/api/schedule/plans/${fy}${path}`, data: body })).data,
    onSuccess: (d) => {
      qc.setQueryData(key(tid, 'plan', fy), d)
      void qc.invalidateQueries({ queryKey: ['governance-inbox'] })
    },
  })
}

export function useSaveTemplates() {
  const tid = useActiveTenantId()
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (rows: TemplateRow[]) => (await apiClient.put('/api/schedule/templates', rows)).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: key(tid, 'templates') }),
  })
}

export const errDetail = (e: unknown, f: string) => {
  const d = (e as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
  if (typeof d === 'string') return d
  if (Array.isArray(d)) return (d[0] as { msg?: string })?.msg?.replace(/^Value error, /, '') ?? f
  return f
}
