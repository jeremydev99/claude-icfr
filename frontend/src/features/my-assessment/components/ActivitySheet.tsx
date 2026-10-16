import { useEffect, useRef, useState } from 'react'
import { ClipboardPaste, Download, Loader2, Paperclip, Plus, Trash2, X } from 'lucide-react'
import { toast } from 'sonner'
import { useAuthStore } from '@/features/auth/store'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from '@/components/ui/sheet'
import { Textarea } from '@/components/ui/textarea'
import { errorDetail } from '@/features/admin/api/PolicyAssignmentApi'
import { validateFile } from '@/features/evidence/evidence.pure'
import { downloadEvidence, useActivity, useControlHistory, useMyAssessmentActions } from '../api'
import {
  canDeleteSample,
  isClipboardName,
  listToMethods,
  METHODS,
  methodsLabel,
  methodsToList,
  pastedFileName,
  RESULT_LABEL,
  sampleMissing,
  STAGE_LABEL,
  STATE_LABEL,
  submitBlockers,
} from '../myAssessment.pure'
import type { ActivityRead, SampleRead, WorklistRow } from '../types'

const NONE = '__none__'

/**
 * 통제 1건의 테스트 — 테스트 방법·결론 + 샘플마다 식별·결과·증빙. 필요 샘플 수만큼 채워야 제출된다(마스터 결정).
 * 고칠 수 있는지·제출할 수 있는지의 최종 판정은 서버다. 화면은 미리 알려 주기만 한다.
 */
export default function ActivitySheet({ cycleId, cycleOpen, row, onClose }: {
  cycleId: string
  cycleOpen: boolean
  row: WorklistRow | null
  onClose: () => void
}) {
  const me = useAuthStore((s) => s.user)
  const actions = useMyAssessmentActions()
  const { data: act, isLoading } = useActivity(row?.activity_id ?? null)
  const { data: history = [] } = useControlHistory(row ? cycleId : null, row?.control_id ?? null)
  const isOwner = Boolean(row && me && row.owner_id === me.id)
  const editable = Boolean(act && act.status === 'draft' && cycleOpen && me && act.performed_by_id === me.id && me.can_write)
  const canStart = Boolean(row && isOwner && cycleOpen && me?.can_write && row.state !== 'draft')

  const fail = (fallback: string) => (e: unknown) => toast.error(errorDetail(e, fallback))

  const start = () => row && actions.start.mutate(
    { cycleId, controlId: row.control_id, kind: row.activity_kind },
    { onSuccess: () => toast.success('작성을 시작했습니다'), onError: fail('작성을 시작하지 못했습니다') },
  )

  const required = row?.required_samples ?? 1
  const past = history.filter((h) => h.id !== act?.id).slice().reverse()

  return (
    <Sheet open={Boolean(row)} onOpenChange={(o) => !o && onClose()}>
      <SheetContent className="w-full overflow-y-auto sm:max-w-3xl">
        {row && (
          <>
            <SheetHeader>
              <SheetTitle>{row.control_code} {row.control_name}</SheetTitle>
              <SheetDescription>
                필요 샘플 <b>{required}건</b> ({row.sample_basis}) · 통제책임자 {row.owner_name ?? '미배정'} · {STATE_LABEL[row.state]}
              </SheetDescription>
            </SheetHeader>

            <div className="mt-4 space-y-6 text-sm">
              <section className="rounded-md border bg-muted/30 p-3 space-y-1">
                <p className="font-medium">RCM 테스트 방법</p>
                {row.rcm_control_status && (
                  <details open className="rounded border bg-background/60 p-2">
                    <summary className="cursor-pointer text-muted-foreground">통제현황</summary>
                    <p className="mt-1 max-h-60 overflow-y-auto whitespace-pre-wrap">{row.rcm_control_status}</p>
                  </details>
                )}
                <p><span className="text-muted-foreground">방법</span> {methodsLabel(row.rcm_test_methods)}</p>
                <p><span className="text-muted-foreground">모집단</span> {row.rcm_population ?? '-'}</p>
                <p className="whitespace-pre-wrap"><span className="text-muted-foreground">절차</span> {row.rcm_test_procedure ?? '-'}</p>
              </section>

              {!row.activity_id && (
                <div className="space-y-2">
                  <p className="text-muted-foreground">아직 작성된 테스트가 없습니다.</p>
                  {canStart && (
                    <Button onClick={start} disabled={actions.start.isPending}>
                      {actions.start.isPending && <Loader2 className="mr-1 h-4 w-4 animate-spin" />}테스트 작성 시작
                    </Button>
                  )}
                </div>
              )}

              {row.activity_id && isLoading && <Loader2 className="h-5 w-5 animate-spin" />}

              {act && (
                <>
                  <ActivityForm act={act} editable={editable} />
                  <SamplesTable act={act} editable={editable} required={required} cycleId={cycleId} controlCode={row.control_code} />
                  <Footer act={act} row={row} editable={editable} required={required} canRedo={canStart && act.status === 'submitted'}
                    onRedo={start} />
                </>
              )}

              {past.length > 0 && (
                <section className="space-y-2">
                  <p className="font-medium">이전 기록 (재수행 전)</p>
                  <ul className="space-y-1 text-muted-foreground">
                    {past.map((h) => (
                      <li key={h.id}>
                        {h.submitted_at?.slice(0, 10) ?? h.performed_at.slice(0, 10)} · {h.performed_by_name} ·{' '}
                        {h.status === 'draft' ? '작성 중' : `제출 — ${RESULT_LABEL[h.result ?? ''] ?? h.result ?? '-'}`}
                        {' '}· 샘플 {h.samples.length}건
                      </li>
                    ))}
                  </ul>
                </section>
              )}
            </div>
          </>
        )}
      </SheetContent>
    </Sheet>
  )
}

function ActivityForm({ act, editable }: { act: ActivityRead; editable: boolean }) {
  const { patchActivity } = useMyAssessmentActions()
  const [population, setPopulation] = useState(act.population ?? '')
  const [procedure, setProcedure] = useState(act.procedure ?? '')
  const [note, setNote] = useState(act.note ?? '')
  useEffect(() => {
    setPopulation(act.population ?? '')
    setProcedure(act.procedure ?? '')
    setNote(act.note ?? '')
  }, [act.id, act.population, act.procedure, act.note])

  const save = (body: Parameters<typeof patchActivity.mutate>[0]['body']) =>
    patchActivity.mutate({ id: act.id, body }, { onError: (e) => toast.error(errorDetail(e, '저장하지 못했습니다')) })
  const methods = methodsToList(act.test_methods)

  if (!editable) {
    return (
      <section className="space-y-1">
        <p className="font-medium">테스트 기록 <Badge variant="outline">{act.status === 'draft' ? '작성 중' : '제출됨'}</Badge></p>
        <p><span className="text-muted-foreground">작성</span> {act.performed_by_name} {act.submitted_at ? `· 제출 ${act.submitted_at.slice(0, 10)}` : ''}</p>
        <p><span className="text-muted-foreground">방법</span> {methodsLabel(act.test_methods)}</p>
        <p><span className="text-muted-foreground">모집단</span> {act.population ?? '-'}</p>
        <p className="whitespace-pre-wrap"><span className="text-muted-foreground">절차</span> {act.procedure ?? '-'}</p>
        <p><span className="text-muted-foreground">결론</span> {RESULT_LABEL[act.result ?? ''] ?? '-'}</p>
        {act.note && <p className="whitespace-pre-wrap"><span className="text-muted-foreground">의견</span> {act.note}</p>}
      </section>
    )
  }
  return (
    <section className="space-y-3">
      <p className="font-medium">테스트 기록 <Badge variant="secondary">작성 중</Badge></p>
      <div className="flex flex-wrap gap-4">
        {METHODS.map((m) => (
          <label key={m.value} className="flex items-center gap-1.5">
            <Checkbox checked={methods.includes(m.value)} onCheckedChange={(v) =>
              save({ test_methods: listToMethods(v ? [...methods, m.value] : methods.filter((x) => x !== m.value)) })} />
            {m.label}
          </label>
        ))}
      </div>
      <div className="space-y-1">
        <Label>모집단</Label>
        <Input value={population} onChange={(e) => setPopulation(e.target.value)}
          onBlur={() => population !== (act.population ?? '') && save({ population })} />
      </div>
      <div className="space-y-1">
        <Label>테스트 절차</Label>
        <Textarea rows={3} value={procedure} onChange={(e) => setProcedure(e.target.value)}
          onBlur={() => procedure !== (act.procedure ?? '') && save({ procedure })} />
      </div>
      <div className="flex flex-wrap items-end gap-3">
        <div className="space-y-1">
          <Label>테스트 결론</Label>
          <Select value={act.result ?? NONE} onValueChange={(v) => save({ result: v === NONE ? null : v })}>
            <SelectTrigger className="w-40"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value={NONE}>선택</SelectItem>
              {Object.entries(RESULT_LABEL).map(([v, l]) => <SelectItem key={v} value={v}>{l}</SelectItem>)}
            </SelectContent>
          </Select>
        </div>
        <div className="flex-1 space-y-1 min-w-[200px]">
          <Label>의견</Label>
          <Input value={note} onChange={(e) => setNote(e.target.value)}
            onBlur={() => note !== (act.note ?? '') && save({ note })} />
        </div>
      </div>
    </section>
  )
}

function SamplesTable({ act, editable, required, cycleId, controlCode }: {
  act: ActivityRead; editable: boolean; required: number; cycleId: string; controlCode: string | null
}) {
  const { addSample } = useMyAssessmentActions()
  return (
    <section className="space-y-2">
      <div className="flex items-center justify-between">
        <p className="font-medium">
          샘플 ({act.samples.length}건 / 필요 {required}건)
          {editable && <span className="ml-2 text-xs font-normal text-muted-foreground">캡처는 「캡처 붙여넣기」를 누르고 Ctrl+V</span>}
        </p>
        {editable && (
          <Button size="sm" variant="outline" disabled={addSample.isPending}
            onClick={() => addSample.mutate(act.id, { onError: (e) => toast.error(errorDetail(e, '샘플을 추가하지 못했습니다')) })}>
            <Plus className="mr-1 h-4 w-4" />샘플 추가
          </Button>
        )}
      </div>
      <div className="space-y-2">
        {act.samples.map((s) => (
          <SampleRow key={s.id} s={s} act={act} editable={editable} cycleId={cycleId} controlCode={controlCode}
            deletable={editable && canDeleteSample(act.samples.length, required)} />
        ))}
      </div>
    </section>
  )
}

function SampleRow({ s, act, editable, deletable, cycleId, controlCode }: {
  s: SampleRead; act: ActivityRead; editable: boolean; deletable: boolean; cycleId: string; controlCode: string | null
}) {
  const { patchSample, deleteSample, upload, unlink } = useMyAssessmentActions()
  const [label, setLabel] = useState(s.label ?? '')
  const fileRef = useRef<HTMLInputElement>(null)
  const [pasteReady, setPasteReady] = useState(false)
  useEffect(() => setLabel(s.label ?? ''), [s.id, s.label])
  const err = (fallback: string) => ({ onError: (e: unknown) => toast.error(errorDetail(e, fallback)) })
  const save = (body: Parameters<typeof patchSample.mutate>[0]['body']) => patchSample.mutate({ id: s.id, body }, err('저장하지 못했습니다'))
  const missing = sampleMissing(s)

  // 파일 선택·붙여넣기 공통 — 클라이언트 검증(50MB·형식) 후 차례로 올린다. 최종 판정은 서버
  const uploadFiles = async (files: File[]) => {
    const now = new Date()
    for (const [i, f] of files.entries()) {
      const named = isClipboardName(f.name)
        ? new File([f], pastedFileName(f.name, f.type, controlCode, s.seq, now, files.length > 1 ? i : 0), { type: f.type })
        : f
      const bad = validateFile(named)
      if (bad) { toast.error(`${named.name}: ${bad}`); continue }
      try {
        await upload.mutateAsync({ cycleId, controlId: act.control_id, sampleId: s.id, file: named })
      } catch (e) {
        toast.error(errorDetail(e, '증빙을 올리지 못했습니다'))
      }
    }
  }
  // Ctrl+V(2026-10-16, 조사 2) — 이 샘플 줄에 포커스가 있을 때만. 입력칸 안의 붙여넣기·텍스트 붙여넣기는 건드리지 않는다
  const onPaste = (e: React.ClipboardEvent<HTMLDivElement>) => {
    if (!editable || upload.isPending) return
    const t = e.target as HTMLElement
    if (t.closest('input, textarea, [contenteditable="true"]')) return
    const files = Array.from(e.clipboardData.files)
    if (files.length === 0) return
    e.preventDefault()
    void uploadFiles(files)
  }

  return (
    <div className={editable ? 'rounded-md border p-2 outline-none focus-visible:ring-2 focus-visible:ring-ring focus:border-primary' : 'rounded-md border p-2'}
      tabIndex={editable ? 0 : undefined} onPaste={onPaste}
      title={editable ? '클릭 후 Ctrl+V 로 캡처·파일을 이 샘플의 증빙으로 붙여넣기' : undefined}>
      <div className="flex flex-wrap items-center gap-2">
        <span className="w-8 shrink-0 text-center font-medium">{s.seq}</span>
        {editable ? (
          <>
            <Input className="h-8 w-48" placeholder="샘플 식별(전표번호 등)" value={label}
              onChange={(e) => setLabel(e.target.value)} onBlur={() => label !== (s.label ?? '') && save({ label })} />
            <Input className="h-8 w-36" type="date" value={s.sampled_on ?? ''}
              onChange={(e) => save({ sampled_on: e.target.value || null })} />
            <Select value={s.result ?? NONE} onValueChange={(v) => save({ result: v === NONE ? null : v })}>
              <SelectTrigger className="h-8 w-28"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value={NONE}>결과</SelectItem>
                {Object.entries(RESULT_LABEL).map(([v, l]) => <SelectItem key={v} value={v}>{l}</SelectItem>)}
              </SelectContent>
            </Select>
          </>
        ) : (
          <span>{s.label ?? '-'} {s.sampled_on ? `· ${s.sampled_on}` : ''} · {RESULT_LABEL[s.result ?? ''] ?? '-'}</span>
        )}
        <div className="ml-auto flex items-center gap-1">
          {editable && (
            <>
              <input ref={fileRef} type="file" className="hidden" onChange={(e) => {
                const files = Array.from(e.target.files ?? [])
                e.target.value = ''
                void uploadFiles(files)
              }} />
              {/* 캡처 붙여넣기 칸 — 누르면 포커스가 잡히고 Ctrl+V 가 이 샘플로 올라간다(줄의 onPaste 가 받는다) */}
              <div role="button" tabIndex={0} aria-label={`샘플 ${s.seq} 캡처 붙여넣기`}
                onFocus={() => setPasteReady(true)} onBlur={() => setPasteReady(false)}
                className={pasteReady
                  ? 'flex h-8 cursor-text items-center gap-1 rounded-md border-2 border-dashed border-primary bg-primary/5 px-2 text-xs text-primary outline-none'
                  : 'flex h-8 cursor-pointer items-center gap-1 rounded-md border border-dashed px-2 text-xs text-muted-foreground hover:border-primary hover:text-primary'}>
                {upload.isPending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <ClipboardPaste className="h-3.5 w-3.5" />}
                {pasteReady ? '지금 Ctrl+V' : '캡처 붙여넣기'}
              </div>
              <Button size="sm" variant="outline" className="h-8" disabled={upload.isPending} onClick={() => fileRef.current?.click()}>
                <Paperclip className="mr-1 h-4 w-4" />파일
              </Button>
            </>
          )}
          {deletable && (
            <Button size="icon" variant="ghost" className="h-8 w-8" title="샘플 줄 삭제"
              onClick={() => deleteSample.mutate(s.id, err('삭제하지 못했습니다'))}>
              <Trash2 className="h-4 w-4" />
            </Button>
          )}
        </div>
      </div>
      <div className="mt-1 flex flex-wrap gap-2 pl-10">
        {s.evidence.map((ev) => (
          <span key={ev.link_id} className="inline-flex items-center gap-1 rounded bg-muted px-2 py-0.5 text-xs">
            <button type="button" className="inline-flex items-center gap-1 hover:underline"
              onClick={() => downloadEvidence(ev.file_id, ev.filename).catch(() => toast.error('내려받지 못했습니다'))}>
              <Download className="h-3 w-3" />{ev.title ?? ev.filename}
            </button>
            {editable && (
              <button type="button" title="연결 해제" onClick={() => unlink.mutate(ev.link_id, err('연결을 해제하지 못했습니다'))}>
                <X className="h-3 w-3" />
              </button>
            )}
          </span>
        ))}
        {editable && missing.length > 0 && <span className="text-xs text-amber-600">필요: {missing.join('·')}</span>}
      </div>
    </div>
  )
}

function Footer({ act, row, editable, required, canRedo, onRedo }: {
  act: ActivityRead; row: WorklistRow; editable: boolean; required: number; canRedo: boolean; onRedo: () => void
}) {
  const { submit, discard, approve } = useMyAssessmentActions()
  const blockers = submitBlockers(act, required)
  const err = (fallback: string) => ({ onError: (e: unknown) => toast.error(errorDetail(e, fallback)) })

  return (
    <section className="space-y-3 border-t pt-4">
      {editable && (
        <div className="space-y-2">
          {blockers.length > 0 && (
            <ul className="list-disc pl-5 text-xs text-amber-700">{blockers.map((b) => <li key={b}>{b}</li>)}</ul>
          )}
          <div className="flex gap-2">
            <Button disabled={blockers.length > 0 || submit.isPending}
              onClick={() => submit.mutate(act.id, { onSuccess: () => toast.success('제출했습니다'), ...err('제출하지 못했습니다') })}>
              제출
            </Button>
            <Button variant="ghost" disabled={discard.isPending}
              onClick={() => window.confirm('작성 중인 기록을 버릴까요? 올린 증빙 파일은 회차 증빙에 남습니다.')
                && discard.mutate(act.id, err('버리지 못했습니다'))}>
              작성 취소
            </Button>
          </div>
          <p className="text-xs text-muted-foreground">제출하면 고칠 수 없습니다. 다시 하려면 재수행으로 새 기록을 만듭니다.</p>
        </div>
      )}

      {act.status === 'submitted' && (
        <div className="space-y-2">
          <p className="font-medium">승인</p>
          {act.approvals.length === 0 && <p className="text-muted-foreground">아직 승인 기록이 없습니다.</p>}
          {act.approvals.map((a) => (
            <p key={a.id}>{STAGE_LABEL[a.stage] ?? a.stage} — {a.approved_by_name} · {a.approved_at.slice(0, 10)}{a.note ? ` · ${a.note}` : ''}</p>
          ))}
          {row.pending_stages.length > 0 && (
            <p className="text-muted-foreground">남은 단계: {row.pending_stages.map((s) => STAGE_LABEL[s] ?? s).join(' → ')}</p>
          )}
          {row.sod_blocked && (
            <p className="text-amber-700">{row.sod_blocked} — 역할 배정에서 다른 승인자를 지정해야 합니다.</p>
          )}
          <div className="flex gap-2">
            {row.can_approve.map((stage) => (
              <Button key={stage} size="sm" disabled={approve.isPending}
                onClick={() => approve.mutate({ id: act.id, stage }, { onSuccess: () => toast.success('승인했습니다'), ...err('승인하지 못했습니다') })}>
                {STAGE_LABEL[stage] ?? stage}
              </Button>
            ))}
            {canRedo && <Button size="sm" variant="outline" onClick={onRedo}>재수행</Button>}
          </div>
        </div>
      )}
    </section>
  )
}
