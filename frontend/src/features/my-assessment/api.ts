import { useQueries, useQuery, useQueryClient, useMutation } from '@tanstack/react-query'
import apiClient from '@/lib/axios'
import { useActiveTenantId } from '@/features/auth/store'
import type { CycleItem } from '@/features/schedule/api/useSchedule'
import type { ActivityPatch, ActivityRead, SamplePatch, SampleRead, WorklistRow } from './types'

const A = '/api/assessment'
const key = (tenantId: string | null, ...rest: unknown[]) => ['tenant', tenantId ?? 'no-tenant', 'my-assessment', ...rest]

export function useWorklist(cycleId: string | null, mine: boolean) {
  const tenantId = useActiveTenantId()
  return useQuery({
    queryKey: key(tenantId, 'worklist', cycleId, mine),
    queryFn: async () => (await apiClient.get<WorklistRow[]>(`${A}/cycles/${cycleId}/worklist`, { params: { mine } })).data,
    enabled: Boolean(cycleId),
  })
}

export function useActivity(activityId: string | null) {
  const tenantId = useActiveTenantId()
  return useQuery({
    queryKey: key(tenantId, 'activity', activityId),
    queryFn: async () => (await apiClient.get<ActivityRead>(`${A}/activities/${activityId}`)).data,
    enabled: Boolean(activityId),
  })
}

/** 같은 통제·회차의 이전 기록(재수행 이력) — 최신이 마지막 */
export function useControlHistory(cycleId: string | null, controlId: string | null) {
  const tenantId = useActiveTenantId()
  return useQuery({
    queryKey: key(tenantId, 'history', cycleId, controlId),
    queryFn: async () => (await apiClient.get<{ items: ActivityRead[] }>(`${A}/cycles/${cycleId}/activities`,
      { params: { control_id: controlId } })).data.items,
    enabled: Boolean(cycleId && controlId),
  })
}

/** 작성·제출 뒤 목록·상세·이력을 다시 읽는다 — 상태는 서버 판정만 본다 */
export function useMyAssessmentActions() {
  const tenantId = useActiveTenantId()
  const qc = useQueryClient()
  const refresh = () => qc.invalidateQueries({ queryKey: key(tenantId) })
  const opts = { onSuccess: refresh }
  return {
    start: useMutation({
      mutationFn: async (v: { cycleId: string; controlId: string; kind: string }) =>
        (await apiClient.post<ActivityRead>(`${A}/cycles/${v.cycleId}/activities`,
          { control_id: v.controlId, activity_kind: v.kind })).data,
      ...opts,
    }),
    patchActivity: useMutation({
      mutationFn: async (v: { id: string; body: ActivityPatch }) =>
        (await apiClient.patch<ActivityRead>(`${A}/activities/${v.id}`, v.body)).data,
      ...opts,
    }),
    discard: useMutation({
      mutationFn: async (id: string) => { await apiClient.delete(`${A}/activities/${id}`) },
      ...opts,
    }),
    addSample: useMutation({
      mutationFn: async (activityId: string) =>
        (await apiClient.post<SampleRead>(`${A}/activities/${activityId}/samples`, {})).data,
      ...opts,
    }),
    patchSample: useMutation({
      mutationFn: async (v: { id: string; body: SamplePatch }) =>
        (await apiClient.patch<SampleRead>(`${A}/samples/${v.id}`, v.body)).data,
      ...opts,
    }),
    deleteSample: useMutation({
      mutationFn: async (id: string) => { await apiClient.delete(`${A}/samples/${id}`) },
      ...opts,
    }),
    submit: useMutation({
      mutationFn: async (id: string) => (await apiClient.post<ActivityRead>(`${A}/activities/${id}/submit`)).data,
      ...opts,
    }),
    approve: useMutation({
      mutationFn: async (v: { id: string; stage: string; note?: string }) =>
        (await apiClient.post(`${A}/activities/${v.id}/approvals`, { stage: v.stage, note: v.note || null })).data,
      ...opts,
    }),
    upload: useMutation({
      mutationFn: async (v: { cycleId: string; controlId: string; sampleId: string; file: File }) => {
        const fd = new FormData()
        fd.append('cycle_id', v.cycleId)
        fd.append('control_id', v.controlId)
        fd.append('sample_id', v.sampleId)
        fd.append('file', v.file)
        return (await apiClient.post('/api/evidence/files', fd, { headers: { 'Content-Type': 'multipart/form-data' } })).data
      },
      ...opts,
    }),
    unlink: useMutation({
      mutationFn: async (linkId: string) => { await apiClient.delete(`/api/evidence/links/${linkId}`) },
      ...opts,
    }),
  }
}

export async function downloadEvidence(fileId: string, filename: string): Promise<void> {
  const res = await apiClient.get<Blob>(`/api/evidence/files/${fileId}/download`, { responseType: 'blob' })
  const url = URL.createObjectURL(res.data)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

/** 보고서용 — 운영평가 회차들의 테스트 기록(TestRun 대체, 2026-10-15). 회계연도는 회차 평가 기간 시작 연도 */
export interface TestRecord {
  fiscal_year: number
  status: 'in_progress' | 'completed'
  result: string | null
  wtt_summary: string | null
}

export function useTestRecords(cycles: CycleItem[] | undefined) {
  const tenantId = useActiveTenantId()
  const ops = (cycles ?? []).filter((c) => c.kind === 'operation')
  const results = useQueries({
    queries: ops.map((c) => ({
      queryKey: key(tenantId, 'records', c.id),
      queryFn: async () => (await apiClient.get<{ items: ActivityRead[] }>(`${A}/cycles/${c.id}/activities`,
        { params: { limit: 1000 } })).data.items,
    })),
  })
  const data: TestRecord[] = []
  ops.forEach((c, i) => {
    for (const a of results[i]?.data ?? []) {
      if (a.activity_kind !== 'test') continue
      data.push({
        fiscal_year: Number(c.period_start.slice(0, 4)),
        status: a.status === 'submitted' ? 'completed' : 'in_progress',
        result: a.result === 'na' ? 'n/a' : a.result,
        wtt_summary: a.procedure,
      })
    }
  })
  return {
    data,
    isLoading: results.some((r) => r.isLoading),
    isError: results.some((r) => r.isError),
  }
}
