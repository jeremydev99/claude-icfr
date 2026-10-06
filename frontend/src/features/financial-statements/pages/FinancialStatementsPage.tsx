import { cn } from '@/lib/utils'
import { useFiscal } from '@/lib/useFiscal'
import OpenProposalsCard from '@/features/proposals/OpenProposalsCard'
import EmptyState from '@/components/illustration/EmptyState'
import { useEffect, useMemo, useState } from 'react'
import { toast } from 'sonner'
import { Loader2, Lock, Upload } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { useAuthStore } from '@/features/auth/store'
import { isIcfrManagerForUser } from '@/features/auth/permissions.pure'
import { errorDetail, errorValidation, useFsMeta, useFsStatement, useFsStatements, useFsWrite } from '../api/useFs'
import { UNIT_LABEL, allExpanded, errorsByAccount, formatAmount, initialExpanded, pathTo, usesStatementOrder } from '../fsTree.pure'
import StatementTree from '../components/StatementTree'
import ValidationPanel from '../components/ValidationPanel'
import SuspensePanel from '../components/SuspensePanel'
import UploadDialog from '../components/UploadDialog'
import TemplateMatchPanel from '../components/TemplateMatchPanel'
import type { StatementDetail, ValidationResult } from '../types'

/**
 * 재무제표 화면 (8-D1, ADR-0037 §5) — 회계연도 × 연결/별도 × 종류(BS/PL/CF).
 *
 * 데이터는 엑셀 업로드(8-B)·정산표 결합(8-B2)으로 들어온다. 여기서는 트리 금액·검증·확정/재오픈·
 * 허용 오차·임시계정 해소를 한다. 쓰기는 `icfr_manager` 만(서버도 막는다) — 프론트 판정은 `tenant_roles`.
 */
export default function FinancialStatementsPage() {
  const fiscal = useFiscal()
  const { user } = useAuthStore()
  const isManager = isIcfrManagerForUser(user)
  const { data: meta } = useFsMeta()
  const { data: list, isLoading } = useFsStatements()
  const [year, setYear] = useState<number | null>(null)
  const [basis, setBasis] = useState('separate')
  const [stype, setStype] = useState('BS')
  const [uploadOpen, setUploadOpen] = useState(false)
  const [view, setView] = useState<'amounts' | 'template'>('amounts')
  const uploadDialog = (
    <UploadDialog open={uploadOpen} onOpenChange={setUploadOpen} onDone={(t, y) => {
      if (t) setStype(t)
      if (y) setYear(y)
    }} />
  )
  const uploadButton = isManager && (
    <Button size="sm" onClick={() => setUploadOpen(true)}><Upload className="mr-1 h-4 w-4" />엑셀 업로드</Button>
  )

  const years = useMemo(() => [...new Set((list ?? []).map((s) => s.fiscal_year))].sort((a, b) => b - a), [list])
  const bases = useMemo(() => new Set((list ?? []).filter((s) => s.fiscal_year === year).map((s) => s.basis)), [list, year])
  useEffect(() => {
    if (year === null && years.length) setYear(years[0])
  }, [years, year])
  useEffect(() => {
    if (bases.size && !bases.has(basis)) setBasis([...bases][0])
  }, [bases, basis])

  const current = (list ?? []).find((s) => s.fiscal_year === year && s.basis === basis && s.statement_type === stype)
  const { data: detail, isLoading: loadingDetail } = useFsStatement(current?.id ?? null)
  const typeLabel = (v: string) => meta?.statement_types.find((o) => o.value === v)?.label ?? v

  if (isLoading) return <Loader2 className="m-8 h-5 w-5 animate-spin" />
  if (!list?.length) {
    return (
      <div className="mx-auto max-w-[1400px] space-y-6 p-6 md:p-8">
        <h1 className="text-2xl font-bold tracking-tight">재무제표</h1>
        <EmptyState
          slot="empty-finance"
          title="아직 올린 재무제표가 없습니다"
          description={
            <>
              <p>공시양식(재무상태표·손익계산서·현금흐름표) 엑셀을 올리고, 정산표를 결합하세요.</p>
              {!isManager && <p className="mt-2">업로드는 내부회계관리자가 합니다.</p>}
            </>
          }
          action={isManager ? uploadButton : undefined}
        />
        {uploadDialog}
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-[1400px] space-y-6 p-6 md:p-8">
      <OpenProposalsCard kind="fs_template_link" />
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="text-2xl font-bold tracking-tight">재무제표</h1>
        <select value={year ?? ''} onChange={(e) => setYear(Number(e.target.value))}
          className="h-9 rounded border bg-background px-2 py-1 text-sm leading-normal" aria-label="회계연도">
          {years.map((y) => <option key={y} value={y}>{fiscal.short(y)}</option>)}
        </select>
        {bases.size > 1 && (
          <select value={basis} onChange={(e) => setBasis(e.target.value)}
            className="h-9 rounded border bg-background px-2 py-1 text-sm leading-normal" aria-label="연결·별도">
            {[...bases].map((b) => <option key={b} value={b}>{meta?.bases.find((o) => o.value === b)?.label ?? b}</option>)}
          </select>
        )}
        <div className="flex gap-1">
          {['BS', 'PL', 'CF'].map((t) => {
            const s = (list ?? []).find((x) => x.fiscal_year === year && x.basis === basis && x.statement_type === t)
            return (
              <Button key={t} size="sm" variant={stype === t ? 'default' : 'outline'} disabled={!s}
                onClick={() => setStype(t)}>
                {typeLabel(t)}{s?.status === 'final' && ' ✓'}
              </Button>
            )
          })}
        </div>
        {!isManager && (
          <Badge variant="outline" className="gap-1"><Lock className="h-3 w-3" /> 읽기 전용 · 내부회계관리자만 확정</Badge>
        )}
        <span className="ml-auto">{uploadButton}</span>
      </div>
      {uploadDialog}

      <div className="flex gap-1 border-b">
        {([['amounts', '금액·검증'], ['template', '스코핑 템플릿 연결']] as const).map(([v, l]) => (
          <button key={v} type="button" onClick={() => setView(v)}
            className={view === v ? 'border-b-2 border-primary px-3 py-1.5 text-sm font-medium' : 'px-3 py-1.5 text-sm text-muted-foreground hover:text-foreground'}>
            {l}
          </button>
        ))}
      </div>
      {view === 'template' && <TemplateMatchPanel statementType={stype} canEdit={isManager} />}

      {view === 'amounts' && !current && <EmptyState compact slot="empty-finance" title={`이 연도·구분에 ${typeLabel(stype)}가 없습니다.`} />}
      {view === 'amounts' && current && loadingDetail && <Loader2 className="h-5 w-5 animate-spin" />}
      {view === 'amounts' && detail && <StatementView detail={detail} isManager={isManager} />}
    </div>
  )
}

function StatementView({ detail, isManager }: { detail: StatementDetail; isManager: boolean }) {
  const [expanded, setExpanded] = useState<Set<string>>(() => initialExpanded(detail.tree, 1))
  const [highlight, setHighlight] = useState<string | null>(null)
  const [failed, setFailed] = useState<ValidationResult | null>(null)
  const validation = failed ?? detail.validation
  const errors = useMemo(() => errorsByAccount(validation.errors), [validation])
  const draft = detail.status === 'draft'

  useEffect(() => {
    setExpanded(initialExpanded(detail.tree, 1))
    setFailed(null)
  }, [detail.id]) // eslint-disable-line react-hooks/exhaustive-deps

  // 손익·현금흐름은 공시 순서가 기본(매출부터). 합계 구조는 검증할 때 — 화면 상태만, 저장하지 않는다
  const canOrder = usesStatementOrder(detail.statement_type)
  const [order, setOrder] = useState<'statement' | 'tree'>('statement')

  const select = (accountId: string) => {
    const path = pathTo(detail.tree, accountId)
    if (path) setExpanded((prev) => new Set([...prev, ...path]))
    setHighlight(accountId)
    setTimeout(() => document.getElementById(`fs-row-${accountId}`)?.scrollIntoView({ block: 'center', behavior: 'smooth' }), 50)
  }
  const toggle = (id: string) => setExpanded((prev) => {
    const next = new Set(prev)
    if (next.has(id)) next.delete(id)
    else next.add(id)
    return next
  })

  return (
    <div className="space-y-4">
      <Card>
        <CardContent className="flex flex-wrap items-center gap-x-6 gap-y-2 py-3 text-xs">
          <span>
            상태 <Badge variant={draft ? 'secondary' : 'default'}>{draft ? '작성 중' : '확정'}</Badge>
          </span>
          <span>단위 <b>{UNIT_LABEL[detail.unit] ?? detail.unit}</b> · {detail.currency}</span>
          <ToleranceField detail={detail} editable={isManager && draft} />
          {detail.source_filename && (
            <span className="text-muted-foreground">원천 {detail.source_filename} / {detail.source_sheet}</span>
          )}
          <span className="ml-auto flex gap-2">
            {isManager && <StatusButton detail={detail} onFailed={setFailed} />}
          </span>
        </CardContent>
      </Card>

      <SuspensePanel statementId={detail.id} tree={detail.tree} canEdit={isManager && draft} onSelect={select} />

      <Card>
        <CardContent className="py-3">
          <ValidationPanel validation={validation} onSelect={select} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex-row items-center justify-between py-3">
          <CardTitle className="text-sm">계정별 금액</CardTitle>
          <div className="flex flex-wrap items-center gap-2">
            {canOrder && (
              <div className="flex rounded-md border p-0.5 text-xs" role="group" aria-label="보기 순서">
                {([['statement', '공시 순서'], ['tree', '합계 구조']] as const).map(([v, label]) => (
                  <button key={v} type="button" onClick={() => setOrder(v)} aria-pressed={order === v}
                    title={v === 'statement' ? '매출부터 위에서 아래로 — 공시 재무제표와 같은 순서' : '부모 = 하위 합계 — 금액 검증용'}
                    className={cn('rounded px-2.5 py-1 transition-colors', order === v ? 'bg-primary text-primary-foreground' : 'hover:bg-muted')}>
                    {label}
                  </button>
                ))}
              </div>
            )}
            <Button size="sm" variant="ghost" onClick={() => setExpanded(allExpanded(detail.tree))}>모두 펼치기</Button>
            <Button size="sm" variant="ghost" onClick={() => setExpanded(new Set())}>모두 접기</Button>
          </div>
        </CardHeader>
        <CardContent>
          <StatementTree tree={detail.tree} expanded={expanded} onToggle={toggle} errors={errors} highlightId={highlight}
            order={canOrder ? order : 'tree'} />
        </CardContent>
      </Card>

      {detail.events.length > 0 && (
        <Card>
          <CardHeader className="py-3"><CardTitle className="text-sm">확정·재오픈 이력</CardTitle></CardHeader>
          <CardContent className="space-y-1 text-xs">
            {detail.events.map((ev) => (
              <div key={ev.id} className="flex gap-3">
                <span className="text-muted-foreground">{ev.occurred_at.slice(0, 16).replace('T', ' ')}</span>
                <span>{ev.from_status === 'draft' ? '확정' : '재오픈'}</span>
                {ev.reason && <span className="text-muted-foreground">— {ev.reason}</span>}
                {ev.tolerance !== null && ev.from_status === 'draft' && (
                  <span className="text-muted-foreground">허용 오차 {formatAmount(ev.tolerance)}</span>
                )}
              </div>
            ))}
          </CardContent>
        </Card>
      )}
    </div>
  )
}

function ToleranceField({ detail, editable }: { detail: StatementDetail; editable: boolean }) {
  const [value, setValue] = useState(formatAmount(detail.tolerance))
  const mutation = useFsWrite(detail.id)
  useEffect(() => setValue(formatAmount(detail.tolerance)), [detail.tolerance])
  if (!editable) return <span>허용 오차 <b>{formatAmount(detail.tolerance)}</b></span>
  const commit = () => {
    const v = value.replace(/,/g, '').trim()
    if (v === formatAmount(detail.tolerance).replace(/,/g, '')) return
    if (!/^\d+(\.\d{1,2})?$/.test(v)) {
      toast.error('허용 오차는 0 이상의 숫자(소수 2자리까지)입니다')
      return setValue(formatAmount(detail.tolerance))
    }
    mutation.mutate({ kind: 'tolerance', tolerance: v }, {
      onSuccess: () => toast.success('허용 오차를 바꿨습니다 — 검증을 다시 했습니다'),
      onError: (e) => toast.error(errorDetail(e, '허용 오차를 바꾸지 못했습니다')),
    })
  }
  return (
    <label className="flex items-center gap-1">
      허용 오차
      <Input value={value} onChange={(e) => setValue(e.target.value)} onBlur={commit}
        onKeyDown={(e) => e.key === 'Enter' && commit()} className="h-7 w-24 text-right text-xs" />
    </label>
  )
}

function StatusButton({ detail, onFailed }: { detail: StatementDetail; onFailed: (v: ValidationResult | null) => void }) {
  const [open, setOpen] = useState(false)
  const [reason, setReason] = useState('')
  const mutation = useFsWrite(detail.id)
  const finalizing = detail.status === 'draft'

  const submit = () => {
    if (!finalizing && !reason.trim()) return toast.error('재오픈 사유를 입력하세요')
    mutation.mutate(finalizing ? { kind: 'finalize', reason: reason.trim() || undefined } : { kind: 'reopen', reason: reason.trim() }, {
      onSuccess: () => {
        onFailed(null)
        setOpen(false)
        setReason('')
        toast.success(finalizing ? '확정했습니다' : '재오픈했습니다')
      },
      onError: (e) => {
        onFailed(errorValidation(e))
        setOpen(false)
        toast.error(errorDetail(e, finalizing ? '확정하지 못했습니다' : '재오픈하지 못했습니다'))
      },
    })
  }

  return (
    <>
      <Button size="sm" variant={finalizing ? 'default' : 'outline'}
        disabled={finalizing && !detail.validation.ok} onClick={() => setOpen(true)}
        title={finalizing && !detail.validation.ok ? '검증 오류를 먼저 해결하세요' : undefined}>
        {finalizing ? '확정' : '재오픈'}
      </Button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{finalizing ? '재무제표 확정' : '재무제표 재오픈'}</DialogTitle>
            <DialogDescription>
              {finalizing
                ? '확정하면 금액을 바꿀 수 없습니다(바꾸려면 재오픈). 허용 오차와 차액이 이력에 남습니다.'
                : '재오픈하면 금액을 다시 바꿀 수 있습니다. 사유가 이력에 남습니다.'}
            </DialogDescription>
          </DialogHeader>
          <Textarea value={reason} onChange={(e) => setReason(e.target.value)} rows={3}
            placeholder={finalizing ? '확정 메모 (선택)' : '재오픈 사유 (필수)'} />
          <DialogFooter>
            <Button variant="ghost" onClick={() => setOpen(false)}>취소</Button>
            <Button onClick={submit} disabled={mutation.isPending}>
              {mutation.isPending && <Loader2 className="mr-1 h-4 w-4 animate-spin" />}
              {finalizing ? '확정' : '재오픈'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}
