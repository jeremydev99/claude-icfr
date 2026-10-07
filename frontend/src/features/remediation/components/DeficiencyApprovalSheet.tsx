import { useEffect, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Loader2 } from 'lucide-react'
import { toast } from 'sonner'
import apiClient from '@/lib/axios'
import { queryKeys } from '@/lib/queryKeys'
import { useActiveTenantId } from '@/features/auth/store'
import { useCanWrite } from '@/features/auth/useCanWrite'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from '@/components/ui/sheet'
import { Textarea } from '@/components/ui/textarea'
import ApprovalPanel, { type ApprovalAction } from '@/features/governance/ApprovalPanel'
import GovernanceHistory from '@/features/governance/GovernanceHistory'
import { APPROVAL_STATUS_LABELS, SEVERITY_BADGE_CLASS, SEVERITY_LABELS, type DeficiencyApproval } from '../types'

const BASE = '/api/remediation/deficiencies'

function errorDetail(e: unknown, fallback: string): string {
  const d = (e as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
  return typeof d === 'string' ? d : fallback
}

/**
 * 미비점 평가 결론 + 결재(ADR-0038 2-3). 결론은 작성 중일 때만 고친다. 확정은 결재 승인으로만 되고
 * **재오픈은 없다** — 이후 개선은 개선계획·다음 차수 평가로. 버튼은 서버가 준 `governance.can` 만 본다.
 */
export default function DeficiencyApprovalSheet({ deficiencyId, onOpenChange }: {
  deficiencyId: string | null
  onOpenChange: (open: boolean) => void
}) {
  const tenantId = useActiveTenantId()
  const queryClient = useQueryClient()
  const canWrite = useCanWrite()
  const key = ['deficiency-approval', tenantId, deficiencyId]
  const { data, isLoading } = useQuery({
    queryKey: key,
    queryFn: async () => (await apiClient.get<DeficiencyApproval>(`${BASE}/${deficiencyId}/approval`)).data,
    enabled: Boolean(deficiencyId),
  })
  const [conclusion, setConclusion] = useState('')
  const [busy, setBusy] = useState(false)
  useEffect(() => setConclusion(data?.deficiency.final_conclusion ?? ''), [data?.deficiency.final_conclusion])

  const done = (next: DeficiencyApproval) => {
    queryClient.setQueryData(key, next)
    queryClient.invalidateQueries({ queryKey: queryKeys.remediation.deficienciesAll(tenantId) })
  }
  const run = async (fn: () => Promise<DeficiencyApproval>, ok: string) => {
    setBusy(true)
    try {
      done(await fn())
      toast.success(ok)
    } catch (e) {
      toast.error(errorDetail(e, '처리하지 못했습니다'))
    } finally {
      setBusy(false)
    }
  }
  const post = async (url: string, body: unknown) => (await apiClient.post<DeficiencyApproval>(url, body)).data

  const saveConclusion = async () => {
    setBusy(true)
    try {
      await apiClient.patch(`${BASE}/${deficiencyId}`, { final_conclusion: conclusion.trim() || null })
      await queryClient.invalidateQueries({ queryKey: key })
      queryClient.invalidateQueries({ queryKey: queryKeys.remediation.deficienciesAll(tenantId) })
      toast.success('최종 결론을 저장했습니다')
    } catch (e) {
      toast.error(errorDetail(e, '저장하지 못했습니다'))
    } finally {
      setBusy(false)
    }
  }

  const act = (a: ApprovalAction) => {
    const base = `${BASE}/${deficiencyId}`
    switch (a.kind) {
      case 'submit': return run(() => post(`${base}/transition`, { to_status: 'review', reason: a.reason }), '검토 요청했습니다')
      case 'withdraw': return run(() => post(`${base}/transition`, { to_status: 'draft' }), '회수했습니다')
      case 'review_done': return run(() => post(`${base}/review`, { action: 'done' }), '검토를 마쳤습니다')
      case 'return':
        return run(() => (a.viaReview ? post(`${base}/review`, { action: 'return', reason: a.reason })
          : post(`${base}/transition`, { to_status: 'draft', reason: a.reason })), '반려했습니다')
      case 'approve': return run(() => post(`${base}/transition`, { to_status: 'confirmed', reason: a.reason }), '확정했습니다')
      case 'external': {
        const fd = new FormData()
        fd.append('purpose', 'approve')
        fd.append('approver_body', a.body)
        fd.append('approved_on', a.approvedOn)
        if (a.reference) fd.append('reference', a.reference)
        a.files.forEach((f) => fd.append('files', f))
        return run(() => post(`${base}/external-approval`, fd), '외부 승인을 기록했습니다')
      }
      default:
        toast.error('확정된 미비점 평가는 재오픈하지 않습니다')
    }
  }

  const d = data?.deficiency
  const draft = d?.approval_status === 'draft'
  const dirty = (d?.final_conclusion ?? '') !== conclusion

  return (
    <Sheet open={Boolean(deficiencyId)} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="overflow-y-auto sm:max-w-xl">
        <SheetHeader>
          <SheetTitle>미비점 평가 결론 {d && <span className="font-mono text-base">{d.code}</span>}</SheetTitle>
          <SheetDescription>심각도와 최종 결론을 정해 결재로 확정합니다. 확정 후에는 바꾸지 않습니다.</SheetDescription>
        </SheetHeader>
        {isLoading || !data || !d ? (
          <Loader2 className="m-6 h-5 w-5 animate-spin" />
        ) : (
          <div className="mt-4 space-y-4">
            <div className="flex flex-wrap items-center gap-2 text-sm">
              <Badge variant="outline" className={SEVERITY_BADGE_CLASS[d.severity]}>{SEVERITY_LABELS[d.severity]}</Badge>
              <Badge variant={draft ? 'secondary' : 'default'}>{APPROVAL_STATUS_LABELS[d.approval_status]}</Badge>
              {data.legacy_confirmed && <span className="text-xs text-muted-foreground">(이전 방식 확정 — 결재선 도입 전)</span>}
            </div>
            <p className="whitespace-pre-wrap rounded-md bg-muted/50 p-3 text-sm">{d.description}</p>
            <div className="space-y-1.5">
              <Label htmlFor="final-conclusion">최종 결론</Label>
              <Textarea id="final-conclusion" rows={4} value={conclusion} disabled={!draft || !canWrite || busy}
                onChange={(e) => setConclusion(e.target.value)}
                placeholder="예: 유의적 미비점 — 대체 통제로 보완되지 않음, 개선계획 필요" />
              {draft && canWrite && (
                <div className="flex justify-end">
                  <Button size="sm" variant="outline" disabled={!dirty || busy} onClick={saveConclusion}>결론 저장</Button>
                </div>
              )}
            </div>
            <ApprovalPanel status={d.approval_status} g={data.governance} pending={busy}
              warnBeforeApprove={dirty ? '저장하지 않은 결론 수정이 있습니다 — 저장된 결론으로 처리됩니다.' : undefined}
              onAction={act} />
            <GovernanceHistory url={`${BASE}/${d.id}/governance-events`}
              refreshKey={`${d.approval_status}-${d.updated_at}`} />
          </div>
        )}
      </SheetContent>
    </Sheet>
  )
}
