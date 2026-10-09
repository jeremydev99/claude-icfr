import { useEffect, useState } from 'react'
import { toast } from 'sonner'
import { Check, CircleDot, ChevronRight, Lock, Plus, Send, Settings2, Trash2, Undo2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { cn } from '@/lib/utils'
import { useAuthStore } from '@/features/auth/store'
import { isIcfrManagerForUser } from '@/features/auth/permissions.pure'
import { CATEGORY_LABEL, CATEGORY_STYLE, offsetToCalendar, type PhaseCategory } from '../schedule.pure'
import { fiscalRangeText } from '@/lib/fiscalYear'
import {
  errDetail, usePlanAction, useSaveTemplates, useTemplates,
  type ItemBody, type PlanItem, type PlanResp, type TemplateRow,
} from '../api/usePlan'
import HelpButton from '@/features/help/HelpButton'

const STEP_LABEL: Record<string, string> = { lead: '책임관리자', master: '마스터관리자', ceo: '대표이사' }

/**
 * 연간 일정안(2026-10-06) — 표준·사용자 지정 항목을 표에서 눌러 고치고, 결재선(정책)에 따라 결재받는다.
 * 일정안이 없으면 표준 일정으로 만든다. 표준 일정 자체는 마스터관리자가 '표준 일정 관리'에서 고친다.
 */
export default function PlanPanel({ fy, data }: { fy: number; data: PlanResp }) {
  const user = useAuthStore((s) => s.user)
  const isMaster = isIcfrManagerForUser(user)
  const act = usePlanAction(fy)
  const [edit, setEdit] = useState<PlanItem | 'new' | null>(null)
  const [tplOpen, setTplOpen] = useState(false)
  const [reason, setReason] = useState<'submit' | 'approve' | 'return' | null>(null)
  const p = data.plan
  const run = (method: 'post' | 'put' | 'delete', path: string, body?: unknown, ok?: string) =>
    act.mutate({ method, path, body }, { onSuccess: () => ok && toast.success(ok), onError: (e) => toast.error(errDetail(e, '처리하지 못했습니다')) })

  const line = p && p.approval_line.length ? p.approval_line : data.policy_line.map((s) => ({ step: s, label: STEP_LABEL[s] ?? s }))
  return (
    <Card>
      <CardHeader className="space-y-3 pb-3">
        <div className="flex flex-wrap items-center gap-2">
          <CardTitle className="text-base">{fy} 회계연도 일정안 <span className="text-sm font-normal text-muted-foreground">{fiscalRangeText(fy, data.start_month)}</span></CardTitle>
          <HelpButton k="screen.schedule.plan" />
          {p && <Badge variant={p.status === 'approved' ? 'default' : p.status === 'in_review' ? 'secondary' : 'outline'}>{p.status_label} · {p.version}판</Badge>}
          <span className="ml-auto flex flex-wrap gap-2">
            {isMaster && <Button size="sm" variant="ghost" onClick={() => setTplOpen(true)}><Settings2 className="mr-1.5 h-4 w-4" />표준 일정 관리</Button>}
            {p && data.can.edit && <Button size="sm" variant="outline" onClick={() => setEdit('new')}><Plus className="mr-1.5 h-4 w-4" />일정 추가</Button>}
            {p && data.can.submit && <Button size="sm" onClick={() => setReason('submit')}><Send className="mr-1.5 h-4 w-4" />결재 요청</Button>}
            {p && data.can.approve && <Button size="sm" onClick={() => setReason('approve')}><Check className="mr-1.5 h-4 w-4" />승인</Button>}
            {p && data.can.return && <Button size="sm" variant="outline" onClick={() => setReason('return')}><Undo2 className="mr-1.5 h-4 w-4" />반려</Button>}
          </span>
        </div>
        {/* 결재선 */}
        <ol className="flex flex-wrap items-center gap-1.5 text-xs">
          <li className={cn('rounded-full border px-2.5 py-1', p?.requested_by ? 'border-success/40 bg-success/10 text-success' : 'text-muted-foreground')}>
            작성·요청{p?.requested_by ? ` · ${p.requested_by}` : ''}
          </li>
          {line.length === 0 && <li className="text-muted-foreground">결재 없음(요청 즉시 확정)</li>}
          {line.map((s, i) => {
            const done = p?.approvals[i]
            const cur = p?.status === 'in_review' && p.current_step === i
            return (
              <li key={i} className="flex items-center gap-1.5">
                <ChevronRight className="h-3.5 w-3.5 text-muted-foreground" />
                <span className={cn('inline-flex items-center gap-1 rounded-full border px-2.5 py-1',
                  done && 'border-success/40 bg-success/10 text-success', cur && 'border-primary/40 bg-accent font-semibold', !done && !cur && 'text-muted-foreground')}>
                  {done ? <Check className="h-3 w-3" /> : <CircleDot className="h-3 w-3" />}{s.label}{done ? ` · ${done.name}` : ''}
                </span>
              </li>
            )
          })}
          {Object.values(data.can.why).length > 0 && (
            <li className="ml-2 flex items-center gap-1 text-muted-foreground"><Lock className="h-3 w-3" />{Object.values(data.can.why).join(' · ')}</li>
          )}
        </ol>
        {p?.returned_reason && p.status === 'draft' && <p className="text-sm text-destructive">반려 사유: {p.returned_reason}</p>}
        {p?.status === 'approved' && data.can.edit && <p className="text-xs text-muted-foreground">승인된 일정안을 고치면 새 판(작성 중)이 되어 다시 결재를 받습니다.</p>}
      </CardHeader>
      <CardContent>
        {!p ? (
          <div className="flex flex-col items-center gap-3 rounded-lg border border-dashed py-8 text-center text-sm">
            <p className="text-muted-foreground">{fy} 회계연도 일정안이 아직 없습니다. 아래 그림은 표준 일정입니다.</p>
            {data.can.edit && <Button onClick={() => run('post', '/init', undefined, '표준 일정으로 일정안을 만들었습니다')}>표준 일정으로 {fy} 일정안 만들기</Button>}
          </div>
        ) : (
          <div className="overflow-x-auto rounded-lg border">
            <table className="w-full min-w-[720px] text-sm">
              <thead className="bg-muted/50 text-left">
                <tr>
                  <th className="px-3 py-2 font-semibold">구분</th>
                  <th className="px-3 py-2 font-semibold">일정</th>
                  <th className="px-3 py-2 font-semibold">기간</th>
                  <th className="px-3 py-2 font-semibold">분류</th>
                  <th className="px-3 py-2 font-semibold">설명</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((it) => (
                  <tr key={it.id} onClick={() => data.can.edit && setEdit(it)}
                    className={cn('border-t', data.can.edit && 'cursor-pointer hover:bg-muted/40')} title={data.can.edit ? '눌러서 고치기' : undefined}>
                    <td className="px-3 py-2"><Badge variant={it.kind === 'standard' ? 'secondary' : 'outline'}>{it.kind === 'standard' ? '표준' : '사용자 지정'}</Badge></td>
                    <td className="px-3 py-2 font-medium">
                      <span className={`mr-2 inline-block h-2.5 w-2.5 rounded-full ${CATEGORY_STYLE[it.category as PhaseCategory] ?? 'bg-slate-400'}`} />{it.title}
                    </td>
                    <td className="whitespace-nowrap px-3 py-2 tabular-nums">{it.start_date === it.end_date ? it.start_date : `${it.start_date} ~ ${it.end_date}`}</td>
                    <td className="px-3 py-2 text-muted-foreground">{CATEGORY_LABEL[it.category] ?? it.category}</td>
                    <td className="max-w-[360px] truncate px-3 py-2 text-muted-foreground" title={it.description ?? ''}>{it.description}</td>
                  </tr>
                ))}
                {data.items.length === 0 && <tr><td colSpan={5} className="p-6 text-center text-muted-foreground">일정이 없습니다 — [일정 추가]</td></tr>}
              </tbody>
            </table>
          </div>
        )}
      </CardContent>
      {edit && <ItemDialog fy={fy} startMonth={data.start_month} item={edit === 'new' ? null : edit} busy={act.isPending}
        onClose={() => setEdit(null)}
        onSave={(body) => run(edit === 'new' ? 'post' : 'put', edit === 'new' ? '/items' : `/items/${edit.id}`, body, '저장했습니다')}
        onDelete={edit !== 'new' ? () => { if (window.confirm(`'${edit.title}' 일정을 지울까요?`)) { run('delete', `/items/${edit.id}`, undefined, '지웠습니다'); setEdit(null) } } : undefined} />}
      <ReasonDialog kind={reason} onClose={() => setReason(null)} onOk={(note) => {
        run('post', `/${reason}`, { note }, reason === 'submit' ? '결재를 요청했습니다' : reason === 'approve' ? '승인했습니다' : '반려했습니다')
        setReason(null)
      }} />
      <TemplateEditor open={tplOpen} onOpenChange={setTplOpen} startMonth={data.start_month} />
    </Card>
  )
}

function ItemDialog({ fy, startMonth, item, busy, onClose, onSave, onDelete }: {
  fy: number; startMonth: number; item: PlanItem | null; busy: boolean
  onClose: () => void; onSave: (b: ItemBody) => void; onDelete?: () => void
}) {
  const { data: tpl } = useTemplates()
  const [kind, setKind] = useState<'standard' | 'custom'>(item?.kind ?? 'custom')
  const [code, setCode] = useState(item?.template_code ?? '')
  const [title, setTitle] = useState(item?.kind === 'custom' ? item.title : '')
  const [start, setStart] = useState(item?.start_date ?? `${fy}-${String(startMonth).padStart(2, '0')}-01`)
  const [end, setEnd] = useState(item?.end_date ?? `${fy}-${String(startMonth).padStart(2, '0')}-01`)
  const [desc, setDesc] = useState(item?.description ?? '')
  useEffect(() => {   // 표준 일정을 고르면 그 표준의 기본 기간·설명을 채운다(새로 만들 때만)
    if (item || kind !== 'standard' || !code) return
    const t = tpl?.items.find((x) => x.code === code)
    if (!t) return
    const s = offsetToCalendar(fy, startMonth, t.start_offset)
    const e = offsetToCalendar(fy, startMonth, t.end_offset)
    setStart(`${s.year}-${String(s.month).padStart(2, '0')}-01`)
    setEnd(`${e.year}-${String(e.month).padStart(2, '0')}-${new Date(e.year, e.month, 0).getDate()}`)
    setDesc(t.description ?? '')
  }, [code, kind, item, tpl, fy, startMonth])
  const ok = start && end && end >= start && (kind === 'standard' ? !!code : !!title.trim())
  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose() }}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>{item ? '일정 고치기' : '일정 추가'}</DialogTitle>
          <DialogDescription>저장하면 일정안이 바뀌고, 결재 요청으로 승인받아야 확정됩니다.</DialogDescription>
        </DialogHeader>
        <div className="grid gap-3">
          <div className="flex gap-1 rounded-md border p-1" role="radiogroup" aria-label="구분">
            {(['standard', 'custom'] as const).map((k) => (
              <Button key={k} type="button" size="sm" className="flex-1" variant={kind === k ? 'default' : 'ghost'} onClick={() => setKind(k)}>
                {k === 'standard' ? '표준 일정' : '사용자 지정'}
              </Button>
            ))}
          </div>
          {kind === 'standard' ? (
            <label className="grid gap-1 text-sm">표준 일정
              <select value={code} onChange={(e) => setCode(e.target.value)} className="h-10 rounded-md border bg-background px-2 py-0">
                <option value="">선택</option>
                {tpl?.items.map((t) => <option key={t.code} value={t.code}>{t.name}</option>)}
              </select>
            </label>
          ) : (
            <label className="grid gap-1 text-sm">제목
              <Input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="예: 외부감사인 킥오프 미팅" />
            </label>
          )}
          <div className="grid grid-cols-2 gap-3">
            <label className="grid gap-1 text-sm">시작일<Input type="date" value={start} onChange={(e) => setStart(e.target.value)} /></label>
            <label className="grid gap-1 text-sm">종료일<Input type="date" value={end} min={start} onChange={(e) => setEnd(e.target.value)} /></label>
          </div>
          <label className="grid gap-1 text-sm">설명<Textarea rows={2} value={desc} onChange={(e) => setDesc(e.target.value)} /></label>
        </div>
        <DialogFooter className="gap-2 sm:justify-between">
          {onDelete ? <Button variant="ghost" className="text-destructive" onClick={onDelete}><Trash2 className="mr-1.5 h-4 w-4" />삭제</Button> : <span />}
          <span className="flex gap-2">
            <Button variant="outline" onClick={onClose}>취소</Button>
            <Button disabled={!ok || busy} onClick={() => { onSave({ kind, template_code: kind === 'standard' ? code : null, title: kind === 'custom' ? title.trim() : null, start_date: start, end_date: end, description: desc || null }); onClose() }}>저장</Button>
          </span>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function ReasonDialog({ kind, onClose, onOk }: { kind: 'submit' | 'approve' | 'return' | null; onClose: () => void; onOk: (note: string) => void }) {
  const [text, setText] = useState('')
  const title = kind === 'submit' ? '결재 요청' : kind === 'approve' ? '승인' : '반려'
  const required = kind === 'return'
  return (
    <Dialog open={!!kind} onOpenChange={(o) => { if (!o) { setText(''); onClose() } }}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>{kind === 'return' ? '반려하면 일정안이 작성 중으로 돌아갑니다. 사유가 필요합니다.' : '메모(선택)는 결재 이력에 남습니다.'}</DialogDescription>
        </DialogHeader>
        <Textarea rows={3} value={text} onChange={(e) => setText(e.target.value)} placeholder={required ? '반려 사유' : '메모(선택)'} />
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>취소</Button>
          <Button disabled={required && !text.trim()} onClick={() => { onOk(text.trim()); setText('') }}>{title}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

const CATS = ['planning', 'design', 'operation', 'remediation', 'reporting', 'audit', 'other']

/** 표준 일정 관리 — 마스터관리자. 월은 회계월(1 = 회계연도 첫 달, 13~15 = 익년) */
function TemplateEditor({ open, onOpenChange, startMonth }: { open: boolean; onOpenChange: (o: boolean) => void; startMonth: number }) {
  const { data } = useTemplates()
  const save = useSaveTemplates()
  const [rows, setRows] = useState<TemplateRow[]>([])
  useEffect(() => { if (open && data) setRows(data.items.map((r) => ({ ...r }))) }, [open, data])
  const monthLabel = (o: number) => { const m = ((startMonth - 1 + o - 1) % 12) + 1; return `${o}회계월 (${o > 12 ? '익년 ' : ''}${m}월)` }
  const set = (i: number, patch: Partial<TemplateRow>) => setRows(rows.map((r, j) => (j === i ? { ...r, ...patch } : r)))
  const valid = rows.length > 0 && rows.every((r) => r.name.trim() && r.start_offset <= r.end_offset)
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] max-w-4xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle>표준 일정 관리</DialogTitle>
          <DialogDescription>
            회사 표준 연간 일정입니다. 새 회계연도 일정안을 만들 때 이 목록으로 시작합니다(이미 만든 일정안은 바뀌지 않습니다).
            {data?.builtin && ' 지금은 시스템 기본 8개입니다 — 저장하면 회사 표준이 됩니다.'}
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-2">
          {rows.map((r, i) => (
            <div key={i} className="grid gap-2 rounded-lg border p-3 sm:grid-cols-[1.4fr_0.8fr_1fr_1fr_auto]">
              <Input value={r.name} onChange={(e) => set(i, { name: e.target.value })} placeholder="일정 이름" />
              <select value={r.category} onChange={(e) => set(i, { category: e.target.value as TemplateRow['category'] })} className="h-10 rounded-md border bg-background px-2 py-0 text-sm">
                {CATS.map((c) => <option key={c} value={c}>{CATEGORY_LABEL[c]}</option>)}
              </select>
              <select value={r.start_offset} onChange={(e) => set(i, { start_offset: Number(e.target.value) })} className="h-10 rounded-md border bg-background px-2 py-0 text-sm" aria-label="시작">
                {Array.from({ length: 15 }, (_, k) => k + 1).map((o) => <option key={o} value={o}>시작 {monthLabel(o)}</option>)}
              </select>
              <select value={r.end_offset} onChange={(e) => set(i, { end_offset: Number(e.target.value) })} className="h-10 rounded-md border bg-background px-2 py-0 text-sm" aria-label="종료">
                {Array.from({ length: 15 }, (_, k) => k + 1).map((o) => <option key={o} value={o}>종료 {monthLabel(o)}</option>)}
              </select>
              <Button size="icon" variant="ghost" aria-label="삭제" onClick={() => setRows(rows.filter((_, j) => j !== i))}><Trash2 className="h-4 w-4" /></Button>
              <Input className="sm:col-span-5" value={r.description ?? ''} onChange={(e) => set(i, { description: e.target.value })} placeholder="설명" />
              {r.start_offset > r.end_offset && <p className="text-xs text-destructive sm:col-span-5">종료가 시작보다 빠릅니다</p>}
            </div>
          ))}
          <Button size="sm" variant="outline" onClick={() => setRows([...rows, { code: `custom-${Date.now().toString(36)}`, name: '', category: 'other', start_offset: 1, end_offset: 1, description: '', tasks: [] }])}>
            <Plus className="mr-1 h-4 w-4" />표준 일정 추가
          </Button>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>취소</Button>
          <Button disabled={!valid || save.isPending} onClick={() => save.mutate(rows, {
            onSuccess: () => { toast.success('표준 일정을 저장했습니다'); onOpenChange(false) },
            onError: (e) => toast.error(errDetail(e, '저장하지 못했습니다')),
          })}>저장</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
