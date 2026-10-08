import { useEffect, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Loader2, Lock } from 'lucide-react'
import { toast } from 'sonner'
import apiClient from '@/lib/axios'
import { useActiveTenantId } from '@/features/auth/store'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import ApprovalPanel, { type ApprovalAction } from '@/features/governance/ApprovalPanel'
import GovernanceHistory from '@/features/governance/GovernanceHistory'
import type { GovernanceInfo } from '@/features/governance/types'
import RcmCompare from './RcmCompare'

const BASE = '/api/rcm-years'

export interface RcmYear {
  id: string
  fiscal_year: number
  approval_status: 'draft' | 'review' | 'confirmed'
  version: number
  is_latest: boolean
  snapshots: { version: number; control_count: number; confirmed_by: string | null; confirmed_at: string }[]
  pending_changes: number
  /** 재오픈 후 검토 중 — 직전 확정본 대비 변경 한 줄 */
  diff_summary: string | null
  governance: GovernanceInfo
}

export interface RcmLock { locked: boolean; reason: string | null; fiscal_year: number | null; rcm_year_id: string | null }

const LABEL = { draft: '작성 중', review: '검토 중', confirmed: '확정' } as const

function errorDetail(e: unknown, fallback: string): string {
  const d = (e as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
  return typeof d === 'string' ? d : fallback
}

export function useRcmLock() {
  const tenantId = useActiveTenantId()
  return useQuery({
    queryKey: ['rcm-lock', tenantId],
    queryFn: async () => (await apiClient.get<RcmLock>(`${BASE}/lock`)).data,
  })
}

/** RCM 이 잠겼을 때 화면 위에 보이는 안내 — 버튼이 왜 안 되는지 먼저 알린다. */
export function RcmLockBanner() {
  const { data } = useRcmLock()
  if (!data?.locked) return null
  return (
    <div className="flex items-start gap-2 rounded-md border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900">
      <Lock className="mt-0.5 h-4 w-4 shrink-0" />{data.reason}
    </div>
  )
}

/**
 * 회계연도 RCM 확정(ADR-0038 2-5). 지금 RCM 을 출발점으로 회계연도 RCM 을 시작해 결재로 확정하면 그 시점 RCM 전체가
 * 스냅샷으로 남고, 확정·검토 중에는 RCM 수정이 잠긴다. 바꾸려면 재오픈(다른 마스터 승인, 버전 +1).
 */
export default function RcmYearView() {
  const tenantId = useActiveTenantId()
  const queryClient = useQueryClient()
  const key = ['rcm-years', tenantId]
  const { data: years = [], isLoading } = useQuery({
    queryKey: key,
    queryFn: async () => (await apiClient.get<RcmYear[]>(BASE)).data,
  })
  const [newYear, setNewYear] = useState(String(new Date().getFullYear()))
  const [busy, setBusy] = useState(false)
  // 다음에 시작할 연도 — 가장 최근 회계연도의 다음 해(없으면 올해)
  const latestYear = years[0]?.fiscal_year
  useEffect(() => {
    if (latestYear) setNewYear(String(latestYear + 1))
  }, [latestYear])

  const run = async (fn: () => Promise<unknown>, ok: string) => {
    setBusy(true)
    try {
      await fn()
      queryClient.invalidateQueries({ queryKey: key })
      queryClient.invalidateQueries({ queryKey: ['rcm-lock', tenantId] })
      toast.success(ok)
    } catch (e) {
      toast.error(errorDetail(e, '처리하지 못했습니다'))
    } finally {
      setBusy(false)
    }
  }
  const act = (y: RcmYear, a: ApprovalAction) => {
    const base = `${BASE}/${y.id}`
    const post = (url: string, body: unknown) => apiClient.post(url, body)
    switch (a.kind) {
      case 'submit': return run(() => post(`${base}/transition`, { to_status: 'review', reason: a.reason }), '검토 요청했습니다')
      case 'withdraw': return run(() => post(`${base}/transition`, { to_status: 'draft' }), '회수했습니다')
      case 'review_done': return run(() => post(`${base}/review`, { action: 'done' }), '검토를 마쳤습니다')
      case 'return':
        return run(() => (a.viaReview ? post(`${base}/review`, { action: 'return', reason: a.reason })
          : post(`${base}/transition`, { to_status: 'draft', reason: a.reason })), '반려했습니다')
      case 'approve': return run(() => post(`${base}/transition`, { to_status: 'confirmed', reason: a.reason }), '확정했습니다 — 스냅샷을 저장했습니다')
      case 'reopen_request': return run(() => post(`${base}/reopen-requests`, { reason: a.reason }), '재오픈을 요청했습니다')
      case 'reopen_decide':
        return run(() => post(`${base}/reopen-requests/${a.requestId}/decide`, { approve: a.approve, reason: a.reason }),
          a.approve ? '재오픈을 승인했습니다' : '재오픈을 거절했습니다')
      case 'external': {
        const fd = new FormData()
        fd.append('purpose', a.purpose)
        fd.append('approver_body', a.body)
        fd.append('approved_on', a.approvedOn)
        if (a.reference) fd.append('reference', a.reference)
        a.files.forEach((f) => fd.append('files', f))
        return run(() => post(`${base}/external-approval`, fd), '외부 승인을 기록했습니다')
      }
    }
  }

  if (isLoading) return <Loader2 className="h-5 w-5 animate-spin" />
  const latest = years.find((y) => y.is_latest)

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2 rounded-lg border bg-card p-4 text-sm">
        <span className="text-muted-foreground">
          지금 RCM 을 출발점으로 회계연도 RCM 을 시작합니다. 확정하면 그 시점 RCM 전체가 남고, 확정·검토 중에는 RCM 수정이 잠깁니다.
        </span>
        <span className="ml-auto flex items-center gap-2">
          <Input id="rcm-year" className="h-8 w-24" inputMode="numeric" value={newYear} onChange={(e) => setNewYear(e.target.value)} aria-label="회계연도" />
          <Button size="sm" disabled={busy || !/^\d{4}$/.test(newYear) || latest?.approval_status === 'review'}
            onClick={() => run(() => apiClient.post(BASE, { fiscal_year: Number(newYear) }), `${newYear} 회계연도 RCM 을 시작했습니다`)}>
            회계연도 RCM 시작
          </Button>
        </span>
      </div>

      <RcmCompare years={years} />

      {years.length === 0 && <p className="text-sm text-muted-foreground">아직 시작한 회계연도 RCM 이 없습니다.</p>}

      {years.map((y) => (
        <div key={y.id} className="space-y-3 rounded-xl border bg-card p-4 shadow-card">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-lg font-semibold">{y.fiscal_year} 회계연도 RCM</span>
            <Badge variant={y.approval_status === 'confirmed' ? 'default' : 'secondary'}>{LABEL[y.approval_status]}</Badge>
            {!y.is_latest && <Badge variant="outline">지난 연도 — 확정본 고정</Badge>}
            {y.pending_changes > 0 && y.approval_status === 'draft' && (
              <span className="text-xs text-amber-700">상신된 통제 변경 결재 {y.pending_changes}건 — 끝내야 검토 요청할 수 있습니다</span>
            )}
          </div>
          {y.diff_summary && (
            <p className="rounded-md bg-accent px-3 py-2 text-sm text-accent-foreground">{y.diff_summary} — 아래 확정본 비교에서 자세히 볼 수 있습니다</p>
          )}
          {y.is_latest && (
            <ApprovalPanel status={y.approval_status} g={y.governance} pending={busy} onAction={(a) => act(y, a)} />
          )}
          {y.snapshots.length > 0 && (
            <div className="text-sm">
              <div className="mb-1 font-medium">확정본</div>
              <ul className="space-y-1 text-muted-foreground">
                {y.snapshots.map((s) => (
                  <li key={s.version} className="tabular-nums">
                    v{s.version} · 통제 {s.control_count}건 · {s.confirmed_at.slice(0, 10)}{s.confirmed_by ? ` · 승인 ${s.confirmed_by}` : ''}
                  </li>
                ))}
              </ul>
            </div>
          )}
          <GovernanceHistory url={`${BASE}/${y.id}/governance-events`} refreshKey={`${y.approval_status}-${y.version}`} />
        </div>
      ))}
    </div>
  )
}
