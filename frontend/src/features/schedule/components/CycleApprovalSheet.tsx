import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { AlertTriangle, Loader2, Lock } from 'lucide-react'
import { toast } from 'sonner'
import apiClient from '@/lib/axios'
import { useActiveTenantId } from '@/features/auth/store'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from '@/components/ui/sheet'
import { Textarea } from '@/components/ui/textarea'
import GovernanceHistory from '@/features/governance/GovernanceHistory'
import { BODY_LABELS } from '@/features/governance/governance.pure'
import type { ExternalApprovalRead } from '@/features/governance/types'
import { STATUS_LABEL } from '../schedule.pure'

const BASE = '/api/assessment/cycles'

interface CycleGovernance {
  cycle: { id: string; name: string; status: string; closed_by_name: string | null; approved_by_name: string | null
    closed_at: string | null; approved_at: string | null; incomplete_reason: string | null }
  can_approve: boolean
  can_external_approve: boolean
  why: Record<string, string>
  incomplete_count: number
  fiscal_year: number
  unconfirmed_deficiencies: number
  legacy_approved: boolean
  external_approvals: ExternalApprovalRead[]
}

interface Incomplete { control_id: string; control_code: string | null; missing: string[] }

function errorDetail(e: unknown, fallback: string): string {
  const d = (e as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
  return typeof d === 'string' ? d : fallback
}

/**
 * 평가 회차 마감·최종승인(ADR-0032 §2.5·2.6 + ADR-0038 2-4).
 * 마감은 평가자(전담부서), 최종승인은 마스터관리자 — **마감자는 승인할 수 없다**. 마감자 외 마스터가 없으면
 * 대표이사·이사회 승인 증빙으로 승인한다. 재오픈은 없다(이후 개선은 새 회차). 할 수 있는지는 서버 판정만 본다.
 */
export default function CycleApprovalSheet({ cycleId, onOpenChange }: {
  cycleId: string | null
  onOpenChange: (open: boolean) => void
}) {
  const tenantId = useActiveTenantId()
  const queryClient = useQueryClient()
  const key = ['cycle-governance', tenantId, cycleId]
  const { data: g, isLoading } = useQuery({
    queryKey: key,
    queryFn: async () => (await apiClient.get<CycleGovernance>(`${BASE}/${cycleId}/governance`)).data,
    enabled: Boolean(cycleId),
  })
  const open = g?.cycle.status === 'open'
  const { data: incomplete = [] } = useQuery({
    queryKey: ['cycle-incomplete', tenantId, cycleId],
    queryFn: async () => (await apiClient.get<{ items: Incomplete[] }>(`${BASE}/${cycleId}/incomplete`)).data.items,
    enabled: Boolean(cycleId) && open,
  })
  const [reason, setReason] = useState('')
  const [busy, setBusy] = useState(false)
  const [ext, setExt] = useState({ body: 'board' as 'ceo' | 'board', on: '', reference: '', files: [] as File[] })

  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: key })
    queryClient.invalidateQueries({ predicate: (q) => q.queryKey.includes('cycles') || q.queryKey.includes('incomplete') })
  }
  const run = async (fn: () => Promise<unknown>, ok: string) => {
    setBusy(true)
    try {
      await fn()
      refresh()
      toast.success(ok)
    } catch (e) {
      toast.error(errorDetail(e, '처리하지 못했습니다'))
    } finally {
      setBusy(false)
    }
  }
  const close = () => run(() => apiClient.post(`${BASE}/${cycleId}/close`, { incomplete_reason: reason.trim() || null }), '회차를 마감했습니다')
  const approve = () => run(() => apiClient.post(`${BASE}/${cycleId}/approve`), '최종승인했습니다')
  const external = () => {
    const fd = new FormData()
    fd.append('approver_body', ext.body)
    fd.append('approved_on', ext.on)
    if (ext.reference) fd.append('reference', ext.reference)
    ext.files.forEach((f) => fd.append('files', f))
    return run(() => apiClient.post(`${BASE}/${cycleId}/external-approval`, fd), '외부 승인을 기록했습니다')
  }

  return (
    <Sheet open={Boolean(cycleId)} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="overflow-y-auto sm:max-w-xl">
        <SheetHeader>
          <SheetTitle>회차 마감·최종승인 {g && <span className="text-base font-normal">{g.cycle.name}</span>}</SheetTitle>
          <SheetDescription>마감은 평가자가, 최종승인은 마감하지 않은 마스터관리자가 합니다. 승인 후 재오픈은 없습니다.</SheetDescription>
        </SheetHeader>
        {isLoading || !g ? <Loader2 className="m-6 h-5 w-5 animate-spin" /> : (
          <div className="mt-4 space-y-4 text-sm">
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant={open ? 'default' : 'outline'}>{STATUS_LABEL[g.cycle.status] ?? g.cycle.status}</Badge>
              {g.cycle.closed_by_name && <span className="text-muted-foreground">마감 {g.cycle.closed_by_name}</span>}
              {g.cycle.status === 'approved' && (
                <span className="text-muted-foreground">
                  승인 {g.cycle.approved_by_name ?? (g.external_approvals.length ? '대표이사·이사회(증빙)' : '-')}
                  {g.legacy_approved && ' (이전 방식 승인 — 결재선 도입 전)'}
                </span>
              )}
            </div>

            {open && (
              <div className="space-y-2 rounded-lg border p-3">
                <div className="font-medium">마감</div>
                {incomplete.length > 0 ? (
                  <>
                    <p className="text-destructive">미완 통제 {incomplete.length}건 — 사유를 남겨야 마감됩니다.</p>
                    <ul className="max-h-32 overflow-y-auto text-xs text-muted-foreground">
                      {incomplete.map((i) => <li key={i.control_id}>{i.control_code ?? i.control_id} — 없음: {i.missing.join(', ')}</li>)}
                    </ul>
                    <Textarea rows={2} value={reason} onChange={(e) => setReason(e.target.value)} placeholder="미완 사유 (필수)" />
                  </>
                ) : <p className="text-muted-foreground">미완 통제가 없습니다.</p>}
                <div className="flex justify-end">
                  <Button size="sm" disabled={busy || (incomplete.length > 0 && !reason.trim())} onClick={close}>마감</Button>
                </div>
              </div>
            )}

            {g.cycle.status === 'closed' && (
              <div className="space-y-2 rounded-lg border p-3">
                <div className="font-medium">최종승인</div>
                {g.incomplete_count > 0 && (
                  <p className="flex items-center gap-1 text-amber-700"><AlertTriangle className="h-3.5 w-3.5" />
                    미완 통제 {g.incomplete_count}건 — 사유: {g.cycle.incomplete_reason ?? '-'}</p>
                )}
                {g.unconfirmed_deficiencies > 0 && (
                  <p className="flex items-center gap-1 text-amber-700"><AlertTriangle className="h-3.5 w-3.5" />
                    {g.fiscal_year} 회계연도 미확정 미비점 {g.unconfirmed_deficiencies}건 — 승인은 막지 않습니다</p>
                )}
                {g.why.approve && <p className="flex items-center gap-1 text-muted-foreground"><Lock className="h-3.5 w-3.5" />{g.why.approve}</p>}
                {g.can_approve && (
                  <div className="flex justify-end"><Button size="sm" disabled={busy} onClick={approve}>최종승인</Button></div>
                )}
                {g.can_external_approve && (
                  <div className="grid gap-2 sm:grid-cols-2">
                    <Label className="col-span-full">대표이사·이사회 승인 증빙</Label>
                    <select value={ext.body} onChange={(e) => setExt({ ...ext, body: e.target.value as 'ceo' | 'board' })}
                      className="h-9 rounded border bg-background px-2 text-sm" aria-label="승인 기관">
                      <option value="board">이사회</option><option value="ceo">대표이사</option>
                    </select>
                    <Input type="date" value={ext.on} onChange={(e) => setExt({ ...ext, on: e.target.value })} aria-label="승인일" />
                    <Input className="col-span-full" value={ext.reference} placeholder="예: 제3차 이사회"
                      onChange={(e) => setExt({ ...ext, reference: e.target.value })} />
                    <Input className="col-span-full" type="file" multiple accept="application/pdf,image/*"
                      onChange={(e) => setExt({ ...ext, files: Array.from(e.target.files ?? []) })} />
                    <div className="col-span-full flex justify-end">
                      <Button size="sm" disabled={busy || !ext.on || ext.files.length === 0} onClick={external}>증빙 등록·승인</Button>
                    </div>
                  </div>
                )}
              </div>
            )}

            {g.external_approvals.map((e) => (
              <p key={e.id} className="text-xs text-muted-foreground">
                {BODY_LABELS[e.approver_body]} 승인 {e.approved_on}{e.reference ? ` · ${e.reference}` : ''} · 증빙 {e.files.length}개
              </p>
            ))}
            <GovernanceHistory url={`${BASE}/${g.cycle.id}/governance-events`} refreshKey={g.cycle.status} />
          </div>
        )}
      </SheetContent>
    </Sheet>
  )
}
