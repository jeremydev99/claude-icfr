import { useEffect, useState } from 'react'
import { toast } from 'sonner'
import { AlertTriangle, Loader2, Lock } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { useActiveTenantId, useAuthStore } from '@/features/auth/store'
import { isIcfrManagerForUser } from '@/features/auth/permissions.pure'
import {
  errorDetail,
  useScopingDetail,
  useScopingList,
  useScopingMeta,
  useScopingWrite,
} from '../api/useScoping'
import MaterialityCard from '../components/MaterialityCard'
import AccountsTable from '../components/AccountsTable'
import { ConfirmToggle, TemplateBadge } from '../components/bits'
import type { ScopingDetail, ScopingMeta } from '../types'
import apiClient from '@/lib/axios'
import { useQueryClient } from '@tanstack/react-query'
import { queryKeys } from '@/lib/queryKeys'

/**
 * 스코핑 화면 (6-1, ADR-0034) — 회계연도별.
 *
 * 쓰기 권한은 `icfr_manager` 뿐이다. 서버가 `can_edit` 을 준다(확정 상태면 false).
 * 프론트 판정은 `tenant_roles` 로만 한다 — `can_write` 는 external_auditor 판정이라 쓰지 않는다.
 */
export default function ScopingPage() {
  const { user } = useAuthStore()
  const isManager = isIcfrManagerForUser(user)
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

  const create = async () => {
    const y = window.prompt('새 스코핑의 회계연도', String(new Date().getFullYear()))
    if (!y) return
    try {
      const res = await apiClient.post<ScopingDetail>('/api/scoping', { fiscal_year: Number(y) })
      queryClient.invalidateQueries({ queryKey: queryKeys.scoping.all(tenantId) })
      setSelectedId(res.data.id)
      toast.success(`${y} 회계연도 스코핑을 만들었습니다 — 템플릿 값에는 배지가 붙어 있습니다`)
    } catch (e) {
      toast.error(errorDetail(e, '만들지 못했습니다'))
    }
  }

  if (isLoading || !meta) {
    return <div className="flex items-center gap-2 p-6 text-sm text-muted-foreground"><Loader2 className="h-4 w-4 animate-spin" /> 불러오는 중…</div>
  }

  return (
    <div className="space-y-4 p-6">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h1 className="text-2xl font-semibold">Scoping</h1>
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
            <Button onClick={create}>새 회계연도</Button>
          ) : (
            <Badge variant="secondary" className="gap-1"><Lock className="h-3 w-3" /> 읽기 전용 · 내부회계관리자만 편집</Badge>
          )}
        </div>
      </div>

      {(list ?? []).length === 0 && (
        <Card><CardContent className="py-6 text-sm text-muted-foreground">
          아직 스코핑이 없습니다. 새 회계연도를 만들면 표준 템플릿(계정 192건·질적 평가값·판단 근거)이 복사되고,
          템플릿에서 온 값에는 배지가 붙습니다.
        </CardContent></Card>
      )}

      {detail && (
        <>
          <StatusBar d={detail} meta={meta} write={write} isManager={isManager} />
          {detail.warnings.length > 0 && (
            <div className="rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
              {detail.warnings.map((w) => <div key={w} className="flex items-center gap-1"><AlertTriangle className="h-3.5 w-3.5" />{w}</div>)}
            </div>
          )}
          <MaterialityCard key={`${detail.id}-m`} d={detail} meta={meta} write={write} />
          <Card>
            <CardHeader><CardTitle className="text-base">계정 평가</CardTitle></CardHeader>
            <CardContent><AccountsTable d={detail} meta={meta} write={write} /></CardContent>
          </Card>
          <ReviewCard key={`${detail.id}-r`} d={detail} write={write} />
          <GuidanceCard d={detail} write={write} />
        </>
      )}
    </div>
  )
}

function StatusBar({ d, meta, write, isManager }: {
  d: ScopingDetail; meta: ScopingMeta; write: (m: 'post' | 'patch' | 'delete', p: string, b?: unknown) => void
  isManager: boolean
}) {
  const label = (s: string) => meta.statuses.find((x) => x.value === s)?.label ?? s
  const go = (to: string) => {
    let reason: string | null = null
    if (to === 'confirmed') {
      // 배지가 남아 있어도 막지 않는다 — 개수를 드러내고 사유를 남긴다(ADR-0034 §2.2)
      const warn = d.badge_count > 0
        ? `아직 아무도 검토하지 않은 템플릿 값이 ${d.badge_count}개 있습니다. 검토하지 않은 판단이 그대로 확정됩니다.\n(동의하는 값은 '확인'을 누르면 이 숫자에서 빠집니다)\n\n`
        : ''
      reason = window.prompt(`${warn}확정 사유를 입력하세요 (필수)`)
      if (!reason?.trim()) return
    } else if (d.status === 'confirmed') {
      reason = window.prompt('재오픈 사유를 입력하세요 (필수) — 이력에 남습니다')
      if (!reason?.trim()) return
    }
    write('post', `/${d.id}/transition`, { to_status: to, reason })
  }
  const next: Record<string, Array<[string, string]>> = {
    draft: [['review', '검토 요청']],
    review: [['confirmed', '확정'], ['draft', '작성 중으로 되돌리기']],
    confirmed: [['draft', '재오픈']],
  }
  return (
    <div className="flex flex-wrap items-center gap-2 rounded-md border p-3">
      <span className="text-sm">
        <strong>{d.fiscal_year} 회계연도</strong> · 상태 <Badge variant={d.status === 'confirmed' ? 'default' : 'secondary'}>{label(d.status)}</Badge>
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
      {isManager && (
        <div className="ml-auto flex gap-2">
          {(next[d.status] ?? []).map(([to, text]) => (
            <Button key={to} size="sm" variant={to === 'confirmed' ? 'default' : 'outline'} onClick={() => go(to)}>{text}</Button>
          ))}
        </div>
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
      <CardHeader><CardTitle className="text-base">외부감사인 검토 기록</CardTitle></CardHeader>
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
      <CardHeader><CardTitle className="text-base">가이던스·판단 원칙</CardTitle></CardHeader>
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
