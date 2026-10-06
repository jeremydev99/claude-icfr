import EmptyState from '@/components/illustration/EmptyState'
import { useFiscal } from '@/lib/useFiscal'
import { useEffect, useState } from 'react'
import { toast } from 'sonner'
import { AlertTriangle, Loader2, Lock, RefreshCw } from 'lucide-react'
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription,
  AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { useActiveTenantId, useAuthStore } from '@/features/auth/store'
import { isIcfrStaffForUser } from '@/features/auth/permissions.pure'
import ApprovalPanel, { type ApprovalAction } from '@/features/governance/ApprovalPanel'
import GovernanceHistory from '@/features/governance/GovernanceHistory'
import {
  errorDetail,
  useScopingDetail,
  useScopingList,
  useScopingMeta,
  useScopingWrite,
} from '../api/useScoping'
import MaterialityCard from '../components/MaterialityCard'
import AccountsTable from '../components/AccountsTable'
import CoverageSection from '../components/CoverageSection'
import CreateScopingDialog, { type ScopingSource } from '../components/CreateScopingDialog'
import { ConfirmToggle, TemplateBadge } from '../components/bits'
import type { ScopingDetail, ScopingMeta } from '../types'
import apiClient from '@/lib/axios'
import { useQueryClient } from '@tanstack/react-query'
import { queryKeys } from '@/lib/queryKeys'
import HelpButton from '@/features/help/HelpButton'

/**
 * 스코핑 화면 (6-1, ADR-0034) — 회계연도별.
 *
 * 쓰기 권한은 `icfr_manager` 뿐이다. 서버가 `can_edit` 을 준다(확정 상태면 false).
 * 프론트 판정은 `tenant_roles` 로만 한다 — `can_write` 는 external_auditor 판정이라 쓰지 않는다.
 */
export default function ScopingPage() {
  const { user } = useAuthStore()
  // 작성 권한 = 관리자 1~3단계(ADR-0038). 결재 버튼은 서버가 준 governance.can 으로만 그린다
  const isManager = isIcfrStaffForUser(user)
  const { data: meta } = useScopingMeta()
  const { data: list, isLoading } = useScopingList()
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const current = selectedId ?? list?.[0]?.id ?? null
  const { data: detail } = useScopingDetail(current)
  const mutation = useScopingWrite(current)
  const queryClient = useQueryClient()
  const tenantId = useActiveTenantId()

  useEffect(() => {
    if (!selectedId && list?.[0]) setSelectedId(list[0].id)
  }, [list, selectedId])

  const write = (method: 'post' | 'patch' | 'delete', path: string, body?: unknown) =>
    mutation.mutate({ method, path, body }, { onError: (e) => toast.error(errorDetail(e, '저장하지 못했습니다')) })

  // 결재 동작 → API. 외부 승인은 파일이 있어 FormData 로 직접 보낸다
  const [uploading, setUploading] = useState(false)
  const [reloadOpen, setReloadOpen] = useState(false)
  const act = async (d: ScopingDetail, a: ApprovalAction) => {
    const base = `/${d.id}`
    switch (a.kind) {
      case 'submit': return write('post', `${base}/transition`, { to_status: 'review', reason: a.reason })
      case 'withdraw': return write('post', `${base}/transition`, { to_status: 'draft' })
      case 'review_done': return write('post', `${base}/review`, { action: 'done' })
      case 'return':
        return a.viaReview ? write('post', `${base}/review`, { action: 'return', reason: a.reason })
          : write('post', `${base}/transition`, { to_status: 'draft', reason: a.reason })
      case 'approve': return write('post', `${base}/transition`, { to_status: 'confirmed', reason: a.reason })
      case 'reopen_request': return write('post', `${base}/reopen-requests`, { reason: a.reason })
      case 'reopen_decide':
        return write('post', `${base}/reopen-requests/${a.requestId}/decide`, { approve: a.approve, reason: a.reason })
      case 'external': {
        const fd = new FormData()
        fd.append('purpose', a.purpose)
        fd.append('approver_body', a.body)
        fd.append('approved_on', a.approvedOn)
        if (a.reference) fd.append('reference', a.reference)
        a.files.forEach((f) => fd.append('files', f))
        setUploading(true)
        try {
          const res = await apiClient.post<ScopingDetail>(`/api/scoping${base}/external-approval`, fd)
          queryClient.setQueryData(queryKeys.scoping.detail(tenantId, d.id), res.data)
          queryClient.invalidateQueries({ queryKey: queryKeys.scoping.list(tenantId) })
          toast.success('외부 승인을 기록했습니다')
        } catch (e) {
          toast.error(errorDetail(e, '기록하지 못했습니다'))
        } finally {
          setUploading(false)
        }
      }
    }
  }

  const [createOpen, setCreateOpen] = useState(false)
  const [creating, setCreating] = useState(false)
  const create = async (y: number, source: ScopingSource) => {
    setCreating(true)
    try {
      const res = await apiClient.post<ScopingDetail>('/api/scoping', { fiscal_year: y, source })
      queryClient.invalidateQueries({ queryKey: queryKeys.scoping.all(tenantId) })
      setSelectedId(res.data.id)
      setCreateOpen(false)
      toast.success(source === 'financial_statements'
        ? `${y} 회계연도 스코핑을 재무제표(${y - 1})에서 만들었습니다 — 템플릿 연결에서 온 값에는 배지가 붙어 있습니다`
        : `${y} 회계연도 스코핑을 만들었습니다 — 템플릿 값에는 배지가 붙어 있습니다`)
    } catch (e) {
      toast.error(errorDetail(e, '만들지 못했습니다'))
    } finally {
      setCreating(false)
    }
  }

  if (isLoading || !meta) {
    return <div className="flex items-center gap-2 p-6 text-sm text-muted-foreground"><Loader2 className="h-4 w-4 animate-spin" /> 불러오는 중…</div>
  }

  return (
    <div className="mx-auto max-w-[1400px] space-y-6 p-6 md:p-8">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Scoping</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            중요성 기준을 정하고 유의한 계정과목·주석을 가려냅니다. 대상은 별도재무제표입니다.
          </p>
        </div>
        <div className="flex items-center gap-2">
          {(list ?? []).length > 0 && (
            <select value={current ?? ''} onChange={(e) => setSelectedId(e.target.value)} className="h-9 rounded border px-2 text-sm">
              {(list ?? []).map((s) => (
                <option key={s.id} value={s.id}>
                  {s.fiscal_year} 회계연도 · {meta.statuses.find((x) => x.value === s.status)?.label}
                </option>
              ))}
            </select>
          )}
          {isManager ? (
            <Button onClick={() => setCreateOpen(true)}>새 회계연도</Button>
          ) : (
            <Badge variant="secondary" className="gap-1"><Lock className="h-3 w-3" /> 읽기 전용 · 내부회계 관리자(일반·책임·마스터)만 편집</Badge>
          )}
        </div>
      </div>

      <CreateScopingDialog open={createOpen} onOpenChange={setCreateOpen} onCreate={create} pending={creating} />

      {(list ?? []).length === 0 && (
        <EmptyState
          slot="empty-finance"
          title="아직 스코핑이 없습니다"
          description="새 회계연도를 만들 때 직전 연도 확정 재무제표에서 계정·금액을 가져오거나(권장), 표준 템플릿(계정 192건·질적 평가값·판단 근거)을 복사할 수 있습니다. 템플릿에서 온 값에는 배지가 붙습니다."
        />
      )}

      {detail && (
        <>
          <StatusBar d={detail} meta={meta} />
          {detail.governance?.can.edit && (
            <div className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-dashed bg-card/60 px-4 py-3 text-sm">
              <span className="text-muted-foreground">
                재무제표를 스코핑보다 나중에 올렸거나 수정했다면, FY{detail.base_fiscal_year} 확정 재무제표로 계정·금액·중요성 기준값을 다시 채울 수 있습니다.
              </span>
              <Button size="sm" variant="outline" onClick={() => setReloadOpen(true)} disabled={mutation.isPending}>
                <RefreshCw className="mr-1 h-4 w-4" />재무제표에서 다시 불러오기
              </Button>
            </div>
          )}
          <AlertDialog open={reloadOpen} onOpenChange={setReloadOpen}>
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle>재무제표에서 다시 불러올까요?</AlertDialogTitle>
                <AlertDialogDescription>
                  지금 계정 행 {detail.accounts.length}개와 그 배지·입력값이 FY{detail.base_fiscal_year} 확정 재무제표 기준으로 교체됩니다.
                  템플릿 연결이 있는 계정은 질적 평가 기본값을 다시 가져옵니다. 중요성 기준값(세전이익·매출액·총자산·총자본·총비용·영업현금흐름)도 채웁니다.
                  교체 내역은 변경·결재 이력에 남습니다.
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel>취소</AlertDialogCancel>
                <AlertDialogAction onClick={() => { write('post', `/${detail.id}/reload-from-fs`); setReloadOpen(false) }}>
                  다시 불러오기
                </AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
          {detail.governance && (
            <ApprovalPanel status={detail.status} g={detail.governance} pending={mutation.isPending || uploading}
              warnBeforeApprove={detail.badge_count > 0
                ? `아직 아무도 검토하지 않은 템플릿 값이 ${detail.badge_count}개 있습니다. 검토하지 않은 판단이 그대로 확정됩니다.`
                : undefined}
              onAction={(a) => act(detail, a)} />
          )}
          {detail.warnings.length > 0 && (
            <div className="rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
              {detail.warnings.map((w) => <div key={w} className="flex items-center gap-1"><AlertTriangle className="h-3.5 w-3.5" />{w}</div>)}
            </div>
          )}
          <MaterialityCard key={`${detail.id}-m`} d={detail} meta={meta} write={write} />
          <Card>
            <CardHeader><CardTitle className="flex items-center gap-1 text-base">계정 평가 <HelpButton k="screen.scoping.accounts" /></CardTitle></CardHeader>
            <CardContent><AccountsTable d={detail} meta={meta} write={write} /></CardContent>
          </Card>
          <Card>
            <CardHeader><CardTitle className="flex items-center gap-1 text-base">통제 커버리지 <HelpButton k="screen.scoping.coverage" /></CardTitle></CardHeader>
            <CardContent><CoverageSection scopingId={detail.id} /></CardContent>
          </Card>
          <ReviewCard key={`${detail.id}-r`} d={detail} write={write} />
          <GuidanceCard d={detail} write={write} />
          <GovernanceHistory url={`/api/scoping/${detail.id}/events`} refreshKey={detail.governance?.version + detail.status} />
        </>
      )}
    </div>
  )
}

function StatusBar({ d, meta }: { d: ScopingDetail; meta: ScopingMeta }) {
  const fiscal = useFiscal()
  const label = (s: string) => meta.statuses.find((x) => x.value === s)?.label ?? s
  return (
    <div className="flex flex-wrap items-center gap-2 rounded-md border p-3">
      <span className="text-sm">
        <strong>{fiscal.label(d.fiscal_year)}</strong> · 상태 <Badge variant={d.status === 'confirmed' ? 'default' : 'secondary'}>{label(d.status)}</Badge>
      </span>
      <span className="text-xs text-muted-foreground">
        템플릿 {d.template_code} v{d.template_version} · 기준 FY{d.base_fiscal_year} 결산 ·
        검토 안 한 템플릿 값 <strong className={d.badge_count > 0 ? 'text-sky-700' : ''}>{d.badge_count}</strong>개
        · 확인 {d.origin_counts.confirmed} · 수정 {d.origin_counts.edited}
      </span>
      {d.status === 'confirmed' && (
        <span className="text-xs text-muted-foreground">
          확정 {d.confirmed_at?.slice(0, 10)} · 사유 「{d.confirm_reason}」 · 확정 시 검토 안 한 템플릿 값 {d.confirm_badge_count}개
        </span>
      )}
    </div>
  )
}

/** 감사인 검토 기록 — 검토는 시스템 밖에서 하고 결과를 내부회계관리자가 기록한다. 증빙은 문서명·보관 위치 */
function ReviewCard({ d, write }: { d: ScopingDetail; write: (m: 'post' | 'patch' | 'delete', p: string, b?: unknown) => void }) {
  const [f, setF] = useState({
    review_auditor: d.review_auditor ?? '', review_date: d.review_date ?? '',
    review_opinion: d.review_opinion ?? '', review_evidence_ref: d.review_evidence_ref ?? '',
  })
  const save = () => write('patch', `/${d.id}`, {
    review_auditor: f.review_auditor || null, review_date: f.review_date || null,
    review_opinion: f.review_opinion || null, review_evidence_ref: f.review_evidence_ref || null,
  })
  return (
    <Card>
      <CardHeader><CardTitle className="flex items-center gap-1 text-base">외부감사인 검토 기록 <HelpButton k="screen.scoping.auditor-review" /></CardTitle></CardHeader>
      <CardContent className="grid gap-2 sm:grid-cols-2">
        <input disabled={!d.can_edit} placeholder="감사인" value={f.review_auditor}
          onChange={(e) => setF({ ...f, review_auditor: e.target.value })} className="h-8 rounded border px-2 text-sm" />
        <input disabled={!d.can_edit} type="date" value={f.review_date}
          onChange={(e) => setF({ ...f, review_date: e.target.value })} className="h-8 rounded border px-2 text-sm" />
        <textarea disabled={!d.can_edit} placeholder="검토 의견" value={f.review_opinion} rows={2}
          onChange={(e) => setF({ ...f, review_opinion: e.target.value })} className="rounded border px-2 text-sm sm:col-span-2" />
        <input disabled={!d.can_edit} placeholder="증빙 — 문서명·보관 위치 (파일 첨부는 추후 지원)" value={f.review_evidence_ref}
          onChange={(e) => setF({ ...f, review_evidence_ref: e.target.value })} className="h-8 rounded border px-2 text-sm sm:col-span-2" />
        {d.can_edit && <div><Button size="sm" variant="outline" onClick={save}>검토 기록 저장</Button></div>}
      </CardContent>
    </Card>
  )
}

/** 가이던스·판단 원칙·Notes — 템플릿 문구. 동의하면 항목별 "확인", 고치면 그 문구만 배지가 떨어진다 */
function GuidanceCard({ d, write }: { d: ScopingDetail; write: (m: 'post' | 'patch' | 'delete', p: string, b?: unknown) => void }) {
  const [open, setOpen] = useState<string | null>(null)
  return (
    <Card>
      <CardHeader><CardTitle className="flex items-center gap-1 text-base">가이던스·판단 원칙 <HelpButton k="screen.scoping.guidance" /></CardTitle></CardHeader>
      <CardContent className="space-y-1">
        {d.texts.map((t) => (
          <div key={t.id} className="rounded border">
            <div className="flex w-full items-center justify-between gap-2 px-3 py-1.5 text-sm">
              <button type="button" onClick={() => setOpen(open === t.key ? null : t.key)} className="flex-1 text-left">
                {t.title ?? t.key}<TemplateBadge origin={t.badge} />
              </button>
              <ConfirmToggle origins={[t.badge]} disabled={!d.can_edit}
                onConfirm={(undo) => write('post', `/${d.id}/confirm`, { scope: 'text', target_id: t.id, undo })} />
              <button type="button" onClick={() => setOpen(open === t.key ? null : t.key)}
                className="text-xs text-muted-foreground">{open === t.key ? '접기' : '펼치기'}</button>
            </div>
            {open === t.key && (
              <textarea defaultValue={t.body} disabled={!d.can_edit} rows={8}
                onBlur={(e) => e.target.value !== t.body && e.target.value.trim()
                  && write('patch', `/${d.id}/texts/${encodeURIComponent(t.key)}`, { body: e.target.value })}
                className="w-full whitespace-pre-wrap border-t bg-muted/20 p-3 text-xs disabled:bg-muted/20" />
            )}
          </div>
        ))}
      </CardContent>
    </Card>
  )
}
