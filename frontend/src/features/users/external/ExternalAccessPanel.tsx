import { useState } from 'react'
import { toast } from 'sonner'
import { Check, ClipboardCheck, Copy, Link2, Loader2, MailPlus, ShieldAlert, ShieldCheck } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Checkbox } from '@/components/ui/checkbox'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { useAuthStore } from '@/features/auth/store'
import { isIcfrManagerForUser } from '@/features/auth/permissions.pure'
import { formatDate } from '@/lib/utils'
import { cn } from '@/lib/utils'
import {
  TYPE_OPTIONS, api, useAccessReviews, useExternalAction, useExternalUsers, useInvitations,
  type ExternalType, type ExternalUser, type Invitation,
} from './api'
import { accessState, addDays, reviewOverdue } from './externalAccess.pure'
import MailNotice from '../components/MailNotice'
import HelpButton from '@/features/help/HelpButton'

const err = (e: unknown) => (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail

const TONE: Record<string, string> = {
  ok: 'bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-300 dark:border-emerald-800',
  warn: 'bg-amber-50 text-amber-800 border-amber-200 dark:bg-amber-950/40 dark:text-amber-300 dark:border-amber-800',
  bad: 'bg-rose-50 text-rose-700 border-rose-200 dark:bg-rose-950/40 dark:text-rose-300 dark:border-rose-800',
  muted: 'bg-muted text-muted-foreground border-border',
}
const INV_TONE: Record<Invitation['status'], string> = {
  pending_approval: TONE.warn, approved: TONE.ok, accepted: TONE.muted, revoked: TONE.bad, expired: TONE.muted,
}

/**
 * 외부 사용자(ADR-0039) — 초대(요청 → 마스터 승인 → 링크 1회) · 접근 범위·기간 · 분기 재확인.
 * 책임·마스터관리자가 본다. 승인·연장·재확인은 마스터, 요청·해지는 책임관리자도 할 수 있다(서버가 판정).
 */
export default function ExternalAccessPanel() {
  const user = useAuthStore((s) => s.user)
  const isMaster = isIcfrManagerForUser(user)
  const isSysAdmin = user?.role === 'admin'
  const inv = useInvitations()
  const users = useExternalUsers()
  const reviews = useAccessReviews()
  const [inviteOpen, setInviteOpen] = useState(false)
  const [link, setLink] = useState<LinkInfo | null>(null)
  const [reviewOpen, setReviewOpen] = useState(false)
  const [extend, setExtend] = useState<ExternalUser | null>(null)
  const [revoke, setRevoke] = useState<{ kind: 'inv' | 'user'; id: string; who: string } | null>(null)

  const approve = useExternalAction(api.approve)
  const mfaReset = useExternalAction(api.mfaReset)

  const denied = inv.isError && (inv.error as { response?: { status?: number } })?.response?.status === 403
  if (denied) {
    return <p className="rounded-lg border p-6 text-sm text-muted-foreground">외부 사용자 관리는 책임관리자·마스터관리자만 봅니다.</p>
  }

  const lastReview = reviews.data?.[0]
  const overdue = reviewOverdue(lastReview?.created_at)
  const openInv = (inv.data ?? []).filter((i) => i.status === 'pending_approval' || i.status === 'approved')
  const doneInv = (inv.data ?? []).filter((i) => !openInv.includes(i))

  return (
    <div className="space-y-6">
      {/* 안내 + 동작 */}
      <div className="flex flex-wrap items-start justify-between gap-3">
        <p className="max-w-3xl text-sm text-muted-foreground">
          PA회계법인·외부감사인·감사위원회·세무/기장대리인을 <b>초대</b>합니다. 요청은 책임·마스터관리자가 하고,
          <b> 마스터관리자가 승인</b>하면(요청자 본인 승인 불가) 72시간짜리 초대 링크가 <b>한 번만</b> 표시됩니다.
          외부 사용자는 2단계 인증이 필수이고, 접근 기간이 지나면 자동으로 막힙니다.
        </p>
        <Button size="sm" onClick={() => setInviteOpen(true)}><MailPlus className="mr-1.5 h-4 w-4" />초대 요청</Button>
      </div>

      {/* 초대 */}
      <section className="space-y-2">
        <h3 className="flex items-center gap-1 text-base font-semibold">진행 중인 초대 <span className="text-muted-foreground">{openInv.length}</span><HelpButton k="screen.users.external-invite" /></h3>
        <div className="overflow-x-auto rounded-lg border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>상태</TableHead><TableHead>이름·이메일</TableHead><TableHead>유형·소속</TableHead>
                <TableHead>접근 기간</TableHead><TableHead>요청·승인</TableHead><TableHead className="text-right">처리</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {inv.isLoading && <TableRow><TableCell colSpan={6} className="py-6 text-center"><Loader2 className="mx-auto h-4 w-4 animate-spin" /></TableCell></TableRow>}
              {!inv.isLoading && openInv.length === 0 && (
                <TableRow><TableCell colSpan={6} className="py-6 text-center text-sm text-muted-foreground">진행 중인 초대가 없습니다</TableCell></TableRow>
              )}
              {openInv.map((i) => (
                <TableRow key={i.id}>
                  <TableCell><Badge variant="outline" className={INV_TONE[i.status]}>{i.status_label}</Badge>
                    {i.status === 'approved' && i.token_expires_at && (
                      <p className="mt-1 text-xs text-muted-foreground">링크 ~{formatDate(i.token_expires_at)}</p>)}
                  </TableCell>
                  <TableCell><p className="font-medium">{i.display_name}</p><p className="text-xs text-muted-foreground">{i.email}</p></TableCell>
                  <TableCell><p>{i.type_label}</p><p className="text-xs text-muted-foreground">{i.organization}</p></TableCell>
                  <TableCell className="whitespace-nowrap text-sm">{i.valid_from} ~ {i.valid_until}</TableCell>
                  <TableCell className="text-sm">{i.requested_by ?? '-'}{i.approved_by && <span className="text-muted-foreground"> → {i.approved_by}</span>}</TableCell>
                  <TableCell className="space-x-1.5 whitespace-nowrap text-right">
                    {i.status === 'pending_approval' && isMaster && (
                      <Button size="sm" disabled={approve.isPending} onClick={() => approve.mutate(i.id, {
                        onSuccess: (r) => r.invite_url && setLink({
                          url: r.invite_url, who: `${r.organization} ${r.display_name}`,
                          email: r.email, mailSent: r.mail_sent, mailError: r.mail_error,
                        }),
                        onError: (e) => toast.error(err(e) ?? '승인하지 못했습니다'),
                      })}>승인·링크 발급</Button>
                    )}
                    <Button size="sm" variant="ghost" className="text-destructive"
                      onClick={() => setRevoke({ kind: 'inv', id: i.id, who: `${i.organization} ${i.display_name}` })}>취소</Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      </section>

      {/* 외부 사용자 */}
      <section className="space-y-2">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h3 className="flex items-center gap-1 text-base font-semibold">외부 사용자 <span className="text-muted-foreground">{users.data?.length ?? 0}</span><HelpButton k="screen.users.external" /></h3>
          <div className="flex items-center gap-2 text-sm">
            <span className={cn('inline-flex items-center gap-1.5', overdue ? 'text-amber-700 dark:text-amber-300' : 'text-muted-foreground')}>
              {overdue ? <ShieldAlert className="h-4 w-4" /> : <ClipboardCheck className="h-4 w-4" />}
              {lastReview
                ? `마지막 재확인 ${formatDate(lastReview.created_at)} · ${lastReview.reviewed_by ?? ''}`
                : '재확인 기록 없음'}
              {overdue && ' — 분기 재확인 필요'}
            </span>
            {isMaster && <Button size="sm" variant="outline" onClick={() => setReviewOpen(true)}>재확인 기록</Button>}
            <HelpButton k="screen.users.external-review" label="분기 재확인 설명 보기" />
          </div>
        </div>
        <div className="overflow-x-auto rounded-lg border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>상태</TableHead><TableHead>이름·이메일</TableHead><TableHead>유형·소속</TableHead>
                <TableHead>접근 기간</TableHead><TableHead>2단계 인증</TableHead><TableHead>마지막 로그인</TableHead>
                <TableHead className="text-right">처리</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {!users.isLoading && (users.data ?? []).length === 0 && (
                <TableRow><TableCell colSpan={7} className="py-6 text-center text-sm text-muted-foreground">아직 외부 사용자가 없습니다 — 초대가 수락되면 여기에 나타납니다</TableCell></TableRow>
              )}
              {(users.data ?? []).map((u) => {
                const st = accessState(u)
                return (
                  <TableRow key={u.id}>
                    <TableCell><Badge variant="outline" className={TONE[st.tone]}>{st.label}</Badge></TableCell>
                    <TableCell><p className="font-medium">{u.display_name}</p><p className="text-xs text-muted-foreground">{u.email}</p></TableCell>
                    <TableCell><p>{u.type_label}</p><p className="text-xs text-muted-foreground">{u.organization}
                      {u.modules?.length ? ` · ${u.modules.map((m) => (m === 'financial_statements' ? '재무제표' : m)).join(', ')}` : ''}</p></TableCell>
                    <TableCell className="whitespace-nowrap text-sm">{u.valid_from} ~ {u.valid_until}</TableCell>
                    <TableCell>{u.mfa_enabled
                      ? <span className="inline-flex items-center gap-1 text-sm text-emerald-700 dark:text-emerald-300"><ShieldCheck className="h-4 w-4" />등록</span>
                      : <span className="text-sm text-amber-700 dark:text-amber-300">미등록</span>}</TableCell>
                    <TableCell className="whitespace-nowrap text-sm">{u.last_login_at ? formatDate(u.last_login_at) : '-'}</TableCell>
                    <TableCell className="space-x-1 whitespace-nowrap text-right">
                      {isMaster && u.status === 'active' && <Button size="sm" variant="outline" onClick={() => setExtend(u)}>기간 변경</Button>}
                      {isSysAdmin && u.mfa_enabled && (
                        <Button size="sm" variant="ghost" disabled={mfaReset.isPending} onClick={() => {
                          if (!window.confirm(`${u.display_name}의 2단계 인증을 초기화할까요? 다음 로그인 때 다시 등록합니다.`)) return
                          mfaReset.mutate(u.user_id, { onSuccess: (r) => toast.success(r.detail), onError: (e) => toast.error(err(e) ?? '초기화하지 못했습니다') })
                        }}>인증 초기화</Button>
                      )}
                      {u.status === 'active' && (
                        <Button size="sm" variant="ghost" className="text-destructive"
                          onClick={() => setRevoke({ kind: 'user', id: u.id, who: `${u.organization} ${u.display_name}` })}>해지</Button>
                      )}
                    </TableCell>
                  </TableRow>
                )
              })}
            </TableBody>
          </Table>
        </div>
      </section>

      {doneInv.length > 0 && (
        <details className="rounded-lg border px-4 py-3 text-sm">
          <summary className="cursor-pointer font-medium">끝난 초대 {doneInv.length}건</summary>
          <ul className="mt-2 space-y-1 text-muted-foreground">
            {doneInv.map((i) => (
              <li key={i.id}>{formatDate(i.created_at)} · {i.organization} {i.display_name} ({i.type_label}) — {i.status_label}</li>
            ))}
          </ul>
        </details>
      )}

      <InviteDialog open={inviteOpen} onOpenChange={setInviteOpen} />
      <LinkDialog link={link} onClose={() => setLink(null)} />
      <ReviewDialog open={reviewOpen} onOpenChange={setReviewOpen} count={users.data?.length ?? 0} />
      <ExtendDialog target={extend} onClose={() => setExtend(null)} />
      <RevokeDialog target={revoke} onClose={() => setRevoke(null)} />
    </div>
  )
}

function InviteDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (o: boolean) => void }) {
  const [f, setF] = useState({ email: '', display_name: '', organization: '', user_type: 'advisor' as ExternalType,
    valid_until: addDays(90), note: '', fs: true })
  const create = useExternalAction(api.invite)
  const set = <K extends keyof typeof f>(k: K, v: (typeof f)[K]) => setF((p) => ({ ...p, [k]: v }))
  const hint = TYPE_OPTIONS.find((t) => t.value === f.user_type)?.hint
  const ready = f.email.includes('@') && f.display_name.trim() && f.organization.trim() && f.valid_until
  const submit = () => create.mutate({
    email: f.email.trim(), display_name: f.display_name.trim(), organization: f.organization.trim(), user_type: f.user_type,
    valid_until: f.valid_until, note: f.note.trim() || null,
    modules: f.user_type === 'specialist' ? (f.fs ? ['financial_statements'] : []) : null,
  }, {
    onSuccess: () => {
      toast.success('초대를 요청했습니다 — 마스터관리자 승인 후 링크가 발급됩니다')
      onOpenChange(false)
      setF((p) => ({ ...p, email: '', display_name: '', note: '' }))
    },
    onError: (e) => toast.error(err(e) ?? '요청하지 못했습니다'),
  })
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>외부 사용자 초대 요청</DialogTitle>
          <DialogDescription>마스터관리자가 승인하면 초대 링크가 발급됩니다. 요청자 본인은 승인할 수 없습니다.</DialogDescription>
        </DialogHeader>
        <div className="grid gap-3">
          <div className="grid gap-1.5">
            <Label>유형</Label>
            <select value={f.user_type} onChange={(e) => set('user_type', e.target.value as ExternalType)}
              className="h-10 rounded-md border border-input bg-background px-3 text-sm">
              {TYPE_OPTIONS.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
            </select>
            {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="grid gap-1.5"><Label>소속</Label>
              <Input value={f.organization} onChange={(e) => set('organization', e.target.value)} placeholder="예: OO회계법인" /></div>
            <div className="grid gap-1.5"><Label>이름</Label>
              <Input value={f.display_name} onChange={(e) => set('display_name', e.target.value)} /></div>
          </div>
          <div className="grid gap-1.5"><Label>이메일</Label>
            <Input type="email" value={f.email} onChange={(e) => set('email', e.target.value)} /></div>
          <div className="grid gap-1.5"><Label>접근 종료일</Label>
            <Input type="date" value={f.valid_until} min={addDays(0)} onChange={(e) => set('valid_until', e.target.value)} />
            <p className="text-xs text-muted-foreground">오늘부터 이 날짜까지만 접속할 수 있습니다. 기본 90일.</p></div>
          {f.user_type === 'specialist' && (
            <label className="flex items-center gap-2 text-sm">
              <Checkbox checked={f.fs} onCheckedChange={(v) => set('fs', v === true)} />재무제표 작성 허용(확정은 내부회계관리자)
            </label>
          )}
          <div className="grid gap-1.5"><Label>메모(선택)</Label>
            <Textarea rows={2} value={f.note} onChange={(e) => set('note', e.target.value)} placeholder="계약·업무 범위 등" /></div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>취소</Button>
          <Button disabled={!ready || create.isPending} onClick={submit}>{create.isPending ? '요청 중…' : '요청'}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

interface LinkInfo { url: string; who: string; email?: string; mailSent?: boolean | null; mailError?: string | null }

function LinkDialog({ link, onClose }: { link: LinkInfo | null; onClose: () => void }) {
  const [copied, setCopied] = useState(false)
  return (
    <Dialog open={!!link} onOpenChange={(o) => { if (!o) { onClose(); setCopied(false) } }}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2"><Link2 className="h-5 w-5" />초대 링크 — {link?.who}</DialogTitle>
          <DialogDescription>
            <b>지금 한 번만</b> 보입니다(서버에는 해시만 저장). 72시간 안에 한 번 쓸 수 있습니다.
            이메일·메신저로 본인에게만 전달하세요.
          </DialogDescription>
        </DialogHeader>
        <MailNotice sent={link?.mailSent} error={link?.mailError} to={link?.email} />
        <code className="select-all break-all rounded-md bg-muted px-3 py-2 font-mono text-sm">{link?.url}</code>
        <DialogFooter>
          <Button onClick={async () => {
            try { await navigator.clipboard.writeText(link?.url ?? ''); setCopied(true) } catch { /* 직접 선택해 복사 */ }
          }}>{copied ? <Check className="mr-1.5 h-4 w-4" /> : <Copy className="mr-1.5 h-4 w-4" />}{copied ? '복사됨' : '링크 복사'}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function ReviewDialog({ open, onOpenChange, count }: { open: boolean; onOpenChange: (o: boolean) => void; count: number }) {
  const [note, setNote] = useState('')
  const review = useExternalAction(api.review)
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>접근 재확인 기록</DialogTitle>
          <DialogDescription>
            현재 외부 사용자 {count}명의 범위·기간이 여전히 필요한지 확인했다는 기록입니다(분기 1회 권장). 그 시점 목록이 함께 보관됩니다.
            필요 없는 사용자는 먼저 해지하세요.
          </DialogDescription>
        </DialogHeader>
        <Textarea rows={3} value={note} onChange={(e) => setNote(e.target.value)} placeholder="확인 내용(선택) — 예: 3분기 정기 확인, 변경 없음" />
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>취소</Button>
          <Button disabled={review.isPending} onClick={() => review.mutate(note, {
            onSuccess: () => { toast.success('재확인을 기록했습니다'); setNote(''); onOpenChange(false) },
            onError: (e) => toast.error(err(e) ?? '기록하지 못했습니다'),
          })}>확인했습니다</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function ExtendDialog({ target, onClose }: { target: ExternalUser | null; onClose: () => void }) {
  const [until, setUntil] = useState('')
  const upd = useExternalAction(api.update)
  const value = until || target?.valid_until || ''
  return (
    <Dialog open={!!target} onOpenChange={(o) => { if (!o) { onClose(); setUntil('') } }}>
      <DialogContent className="max-w-sm">
        <DialogHeader>
          <DialogTitle>접근 기간 변경</DialogTitle>
          <DialogDescription>{target?.organization} {target?.display_name} — 현재 {target?.valid_from} ~ {target?.valid_until}</DialogDescription>
        </DialogHeader>
        <Input type="date" value={value} min={target?.valid_from} onChange={(e) => setUntil(e.target.value)} />
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>취소</Button>
          <Button disabled={!target || upd.isPending || value === target?.valid_until} onClick={() => target && upd.mutate(
            { id: target.id, valid_until: value },
            { onSuccess: () => { toast.success('기간을 바꿨습니다'); onClose(); setUntil('') }, onError: (e) => toast.error(err(e) ?? '바꾸지 못했습니다') },
          )}>저장</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function RevokeDialog({ target, onClose }: { target: { kind: 'inv' | 'user'; id: string; who: string } | null; onClose: () => void }) {
  const [reason, setReason] = useState('')
  const inv = useExternalAction(api.revokeInvite)
  const usr = useExternalAction(api.revokeUser)
  const busy = inv.isPending || usr.isPending
  const done = { onSuccess: () => { toast.success('처리했습니다'); setReason(''); onClose() }, onError: (e: unknown) => toast.error(err(e) ?? '처리하지 못했습니다') }
  return (
    <Dialog open={!!target} onOpenChange={(o) => { if (!o) onClose() }}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>{target?.kind === 'inv' ? '초대 취소' : '접근 해지'} — {target?.who}</DialogTitle>
          <DialogDescription>{target?.kind === 'inv' ? '발급된 링크가 있으면 즉시 무효가 됩니다.' : '다음 요청부터 바로 차단됩니다. 기록은 남습니다.'}</DialogDescription>
        </DialogHeader>
        <Textarea rows={2} value={reason} onChange={(e) => setReason(e.target.value)} placeholder="사유(선택) — 예: 계약 종료" />
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>닫기</Button>
          <Button variant="destructive" disabled={busy} onClick={() => {
            if (!target) return
            if (target.kind === 'inv') inv.mutate({ id: target.id, reason }, done)
            else usr.mutate({ id: target.id, reason }, done)
          }}>{target?.kind === 'inv' ? '초대 취소' : '해지'}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
