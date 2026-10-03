import { useState } from 'react'
import { Check, ChevronRight, CircleDot, FileText, Lock, Upload } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { cn } from '@/lib/utils'
import { approvalSteps, BODY_LABELS } from './governance.pure'
import type { GovernanceInfo } from './types'

export type ApprovalAction =
  | { kind: 'submit'; reason: string | null }
  | { kind: 'withdraw' }
  | { kind: 'review_done' }
  | { kind: 'return'; reason: string; viaReview: boolean }
  | { kind: 'approve'; reason: string }
  | { kind: 'reopen_request'; reason: string }
  | { kind: 'reopen_decide'; approve: boolean; reason: string | null; requestId: string }
  | { kind: 'external'; purpose: 'approve' | 'reopen'; body: 'ceo' | 'board'; approvedOn: string; reference: string; files: File[] }

type Prompt = { title: string; description?: string; required: boolean; confirmLabel: string; onOk: (reason: string) => void }

/**
 * 결재선·결재 버튼 (ADR-0038) — 문서마다 공통. 무엇을 할 수 있는지는 **서버가 준 `g.can`** 만 본다.
 * 못 하는 이유(`g.can.why`)도 그대로 보여 준다 — 버튼이 왜 없는지 모르면 사용자는 오류로 안다.
 */
export default function ApprovalPanel({ status, g, warnBeforeApprove, onAction, pending }: {
  status: 'draft' | 'review' | 'confirmed'
  g: GovernanceInfo
  /** 승인 직전 경고(예: 검토 안 한 템플릿 값 N개) */
  warnBeforeApprove?: string
  onAction: (a: ApprovalAction) => void
  pending?: boolean
}) {
  const [prompt, setPrompt] = useState<Prompt | null>(null)
  const [external, setExternal] = useState<'approve' | 'reopen' | null>(null)
  const c = g.can
  const steps = approvalSteps(status, g)
  const ask = (p: Prompt) => setPrompt(p)
  const why = Object.values(c.why).filter(Boolean)

  return (
    <div className="space-y-3 rounded-xl border bg-card p-4 shadow-card">
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <span className="font-semibold">결재선</span>
        <Badge variant="outline">v{g.version}</Badge>
        <span className="text-xs text-muted-foreground">내 단계: {g.my_tier_label}</span>
      </div>
      <ol className="flex flex-wrap items-center gap-1.5 text-sm">
        {steps.map((s, i) => (
          <li key={s.key} className="flex items-center gap-1.5">
            {i > 0 && <ChevronRight className="h-4 w-4 text-muted-foreground" />}
            <span className={cn('inline-flex items-center gap-1.5 rounded-full border px-3 py-1',
              s.state === 'done' && 'border-success/40 bg-success/10 text-success',
              s.state === 'current' && 'border-primary/40 bg-accent text-accent-foreground font-semibold',
              s.state === 'todo' && 'text-muted-foreground')}>
              {s.state === 'done' ? <Check className="h-3.5 w-3.5" /> : <CircleDot className="h-3.5 w-3.5" />}
              {s.label}{s.who ? ` · ${s.who}` : ''}
            </span>
          </li>
        ))}
      </ol>

      {g.pending_reopen && (
        <div className="rounded-lg border border-warning/40 bg-warning/10 p-3 text-sm">
          <b>재오픈 요청 대기</b> — {g.pending_reopen.requested_by?.name} · 「{g.pending_reopen.reason}」
        </div>
      )}
      {g.external_approvals.length > 0 && (
        <ul className="space-y-1 text-sm">
          {g.external_approvals.map((e) => (
            <li key={e.id} className="flex flex-wrap items-center gap-2">
              <Badge variant="outline">{e.purpose === 'approve' ? '확정' : '재오픈'}</Badge>
              {BODY_LABELS[e.approver_body]} 승인 {e.approved_on}{e.reference ? ` · ${e.reference}` : ''}
              <span className="text-muted-foreground">기록 {e.recorded_by?.name}</span>
              {e.files.map((f) => (
                <a key={f.id} href={`/api/governance/files/${f.id}`} target="_blank" rel="noreferrer"
                  className="inline-flex items-center gap-1 text-primary underline-offset-2 hover:underline"
                  onClick={(ev) => { ev.preventDefault(); openFile(f.id, f.filename) }}>
                  <FileText className="h-3.5 w-3.5" />{f.filename}
                </a>
              ))}
            </li>
          ))}
        </ul>
      )}

      <div className="flex flex-wrap items-center gap-2">
        {c.submit && <Button size="sm" disabled={pending} onClick={() => ask({ title: '검토 요청', required: false,
          description: '요청 후에는 회수하거나 반려되기 전까지 수정할 수 없습니다.', confirmLabel: '검토 요청',
          onOk: (r) => onAction({ kind: 'submit', reason: r || null }) })}>검토 요청</Button>}
        {c.withdraw && <Button size="sm" variant="outline" disabled={pending} onClick={() => onAction({ kind: 'withdraw' })}>요청 회수</Button>}
        {c.review && <Button size="sm" disabled={pending} onClick={() => onAction({ kind: 'review_done' })}>검토 완료</Button>}
        {c.review_return && <Button size="sm" variant="outline" disabled={pending} onClick={() => ask({ title: '반려', required: true,
          confirmLabel: '반려', onOk: (r) => onAction({ kind: 'return', reason: r, viaReview: c.review }) })}>반려</Button>}
        {c.approve && <Button size="sm" disabled={pending} onClick={() => ask({ title: '승인(확정)', required: true,
          description: warnBeforeApprove, confirmLabel: '승인',
          onOk: (r) => onAction({ kind: 'approve', reason: r }) })}>승인(확정)</Button>}
        {c.external_approve && <Button size="sm" disabled={pending} onClick={() => setExternal('approve')}>
          <Upload className="mr-1 h-4 w-4" />대표이사·이사회 승인 증빙 등록</Button>}
        {c.reopen_request && <Button size="sm" variant="outline" disabled={pending} onClick={() => ask({ title: '재오픈 요청', required: true,
          description: '확정본은 이력에 그대로 남고, 승인되면 버전이 올라가 작성 중으로 돌아갑니다.', confirmLabel: '요청',
          onOk: (r) => onAction({ kind: 'reopen_request', reason: r }) })}>재오픈 요청</Button>}
        {c.reopen_decide && g.pending_reopen && (<>
          <Button size="sm" disabled={pending} onClick={() => onAction({ kind: 'reopen_decide', approve: true, reason: null, requestId: g.pending_reopen!.id })}>재오픈 승인</Button>
          <Button size="sm" variant="outline" disabled={pending} onClick={() => ask({ title: '재오픈 거절', required: true, confirmLabel: '거절',
            onOk: (r) => onAction({ kind: 'reopen_decide', approve: false, reason: r, requestId: g.pending_reopen!.id }) })}>거절</Button>
        </>)}
        {c.reopen_external && <Button size="sm" disabled={pending} onClick={() => setExternal('reopen')}>
          <Upload className="mr-1 h-4 w-4" />재오픈 외부 승인 증빙 등록</Button>}
        {why.length > 0 && (
          <span className="flex items-center gap-1 text-xs text-muted-foreground"><Lock className="h-3.5 w-3.5" />{why.join(' · ')}</span>
        )}
      </div>

      <ReasonDialog prompt={prompt} onClose={() => setPrompt(null)} />
      <ExternalDialog purpose={external} onClose={() => setExternal(null)}
        onSubmit={(v) => { onAction({ kind: 'external', purpose: external!, ...v }); setExternal(null) }} />
    </div>
  )
}

/** 증빙은 키가 필요한 API 라 링크로 바로 못 연다 — 인증 헤더를 붙여 받아 새 창으로 */
async function openFile(id: string, name: string) {
  const { default: apiClient } = await import('@/lib/axios')
  const res = await apiClient.get(`/api/governance/files/${id}`, { responseType: 'blob' })
  const url = URL.createObjectURL(res.data as Blob)
  const w = window.open(url, '_blank')
  if (!w) { const a = document.createElement('a'); a.href = url; a.download = name; a.click() }
  setTimeout(() => URL.revokeObjectURL(url), 60_000)
}

function ReasonDialog({ prompt, onClose }: { prompt: Prompt | null; onClose: () => void }) {
  const [text, setText] = useState('')
  const ok = () => { if (prompt && (!prompt.required || text.trim())) { prompt.onOk(text.trim()); setText(''); onClose() } }
  return (
    <Dialog open={!!prompt} onOpenChange={(o) => { if (!o) { setText(''); onClose() } }}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>{prompt?.title}</DialogTitle>
          {prompt?.description && <DialogDescription className="whitespace-pre-line">{prompt.description}</DialogDescription>}
        </DialogHeader>
        <Label htmlFor="gov-reason">사유{prompt?.required ? ' (필수)' : ' (선택)'} — 이력에 남습니다</Label>
        <Textarea id="gov-reason" value={text} onChange={(e) => setText(e.target.value)} rows={3} autoFocus />
        <DialogFooter>
          <Button variant="outline" onClick={() => { setText(''); onClose() }}>취소</Button>
          <Button onClick={ok} disabled={!!prompt?.required && !text.trim()}>{prompt?.confirmLabel}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function ExternalDialog({ purpose, onClose, onSubmit }: {
  purpose: 'approve' | 'reopen' | null
  onClose: () => void
  onSubmit: (v: { body: 'ceo' | 'board'; approvedOn: string; reference: string; files: File[] }) => void
}) {
  const [body, setBody] = useState<'ceo' | 'board'>('board')
  const [on, setOn] = useState(new Date().toISOString().slice(0, 10))
  const [ref, setRef] = useState('')
  const [files, setFiles] = useState<File[]>([])
  return (
    <Dialog open={!!purpose} onOpenChange={(o) => { if (!o) onClose() }}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>{purpose === 'reopen' ? '재오픈 외부 승인 기록' : '대표이사·이사회 승인 기록'}</DialogTitle>
          <DialogDescription>
            시스템 밖에서 이뤄진 승인(대표이사 결재·이사회 보고/결의)을 증빙과 함께 기록합니다. 의사록·결재 문서 스캔(PDF·이미지)이 필요합니다.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-3">
          <div className="flex gap-2">
            {(['board', 'ceo'] as const).map((b) => (
              <Button key={b} type="button" size="sm" variant={body === b ? 'default' : 'outline'} onClick={() => setBody(b)}>{BODY_LABELS[b]}</Button>
            ))}
          </div>
          <div className="space-y-1"><Label htmlFor="ext-on">승인일</Label><Input id="ext-on" type="date" value={on} onChange={(e) => setOn(e.target.value)} /></div>
          <div className="space-y-1"><Label htmlFor="ext-ref">회의·결재 식별 (선택)</Label>
            <Input id="ext-ref" placeholder="예: 제5차 정기이사회" value={ref} onChange={(e) => setRef(e.target.value)} /></div>
          <div className="space-y-1"><Label htmlFor="ext-files">증빙 파일 (필수)</Label>
            <Input id="ext-files" type="file" multiple accept="application/pdf,image/*" onChange={(e) => setFiles(Array.from(e.target.files ?? []))} /></div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>취소</Button>
          <Button disabled={!files.length || !on} onClick={() => onSubmit({ body, approvedOn: on, reference: ref, files })}>기록하고 확정</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
