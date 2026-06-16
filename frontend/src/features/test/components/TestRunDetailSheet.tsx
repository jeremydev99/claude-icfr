import { useState, useRef } from 'react'
import { CheckCircle2, Circle, Loader2, Pencil, Trash2 } from 'lucide-react'
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet'
import { Separator } from '@/components/ui/separator'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import { toast } from 'sonner'
import {
  useTestRunDetail,
  useTestRunHistory,
  useTransitionTestRun,
  useTestSteps,
  useCreateTestStep,
  useUpdateTestStep,
  useDeleteTestStep,
} from '../api/useTestRuns'
import {
  STATUS_LABELS,
  STATUS_BADGE_CLASS,
  RESULT_LABELS,
  RESULT_BADGE_CLASS,
  type TestRun,
  type TestRunStatus,
  type TestStep,
} from '../types'
import type { Control } from '@/features/rcm/types'
import TestRunEditDialog from './TestRunEditDialog'

// ── StepInlineForm ────────────────────────────────────────────

interface StepInlineFormProps {
  initialDescription: string
  initialResult: 'pass' | 'fail'
  onSave: (description: string, result: 'pass' | 'fail') => void
  onCancel: () => void
  isSaving?: boolean
}

function StepInlineForm({ initialDescription, initialResult, onSave, onCancel, isSaving }: StepInlineFormProps) {
  const [description, setDescription] = useState(initialDescription)
  const [result, setResult] = useState<'pass' | 'fail'>(initialResult)
  const composingRef = useRef(false)

  return (
    <div className="rounded-md border p-3 space-y-2 bg-muted/30">
      <Input
        placeholder="단계 설명을 입력하세요"
        value={description}
        onChange={(e) => {
          if (!composingRef.current) setDescription(e.target.value)
        }}
        onCompositionStart={() => { composingRef.current = true }}
        onCompositionEnd={(e) => {
          composingRef.current = false
          setDescription((e.currentTarget as HTMLInputElement).value)
        }}
        autoFocus
      />
      <div className="flex items-center gap-2">
        <Select value={result} onValueChange={(v) => setResult(v as 'pass' | 'fail')}>
          <SelectTrigger className="w-28 h-8">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="pass">적합</SelectItem>
            <SelectItem value="fail">부적합</SelectItem>
          </SelectContent>
        </Select>
        <Button
          size="sm"
          onClick={() => onSave(description, result)}
          disabled={!description.trim() || isSaving}
        >
          {isSaving && <Loader2 className="h-3 w-3 mr-1 animate-spin" />}
          저장
        </Button>
        <Button size="sm" variant="outline" onClick={onCancel}>취소</Button>
      </div>
    </div>
  )
}

// ── TestRunDetailSheet ────────────────────────────────────────

interface Props {
  runId: string | null
  open: boolean
  onOpenChange: (open: boolean) => void
  controlMap?: Record<string, Control>
}

type RunKey = keyof TestRun

const TEST_METHODS: { key: RunKey; label: string }[] = [
  { key: 'method_inspection', label: '검사' },
  { key: 'method_reperformance', label: '재수행' },
  { key: 'method_observation', label: '관찰' },
  { key: 'method_inquiry', label: '질문' },
]

const NEXT_TRANSITION: Record<TestRunStatus, { label: string; to_status: 'in_progress' | 'completed' | 'approved' } | null> = {
  planned: { label: '테스트 시작', to_status: 'in_progress' },
  in_progress: { label: '테스트 완료', to_status: 'completed' },
  completed: { label: '승인', to_status: 'approved' },
  approved: null,
}

const STEP_RESULT_CLASS: Record<'pass' | 'fail', string> = {
  pass: 'bg-green-100 text-green-700 border-green-200',
  fail: 'bg-red-100 text-red-700 border-red-200',
}

const STEP_RESULT_LABEL: Record<'pass' | 'fail', string> = {
  pass: '적합',
  fail: '부적합',
}

function InfoRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="grid grid-cols-[120px_1fr] gap-2 py-1.5 text-sm">
      <span className="text-muted-foreground shrink-0">{label}</span>
      <span className="break-words">{value ?? '—'}</span>
    </div>
  )
}

function SectionTitle({ children }: { children: React.ReactNode }) {
  return <p className="text-sm font-semibold text-foreground mt-6 mb-1">{children}</p>
}

export default function TestRunDetailSheet({ runId, open, onOpenChange, controlMap }: Props) {
  const { data: run, isLoading } = useTestRunDetail(runId)
  const { data: historyData } = useTestRunHistory(runId)
  const { data: stepsData, isLoading: stepsLoading } = useTestSteps(runId)
  const transition = useTransitionTestRun()
  const createStep = useCreateTestStep()
  const updateStep = useUpdateTestStep()
  const deleteStep = useDeleteTestStep()

  const [editOpen, setEditOpen] = useState(false)
  const [addingStep, setAddingStep] = useState(false)
  const [editingStepId, setEditingStepId] = useState<string | null>(null)
  const [deleteStepId, setDeleteStepId] = useState<string | null>(null)

  const ctrl = run ? controlMap?.[run.control_id] : undefined
  const nextTrans = run ? NEXT_TRANSITION[run.status] : null
  const steps = stepsData?.items ?? []
  const isLocked = run?.status === 'approved'

  const handleTransition = () => {
    if (!run || !nextTrans) return
    transition.mutate(
      { id: run.id, payload: { to_status: nextTrans.to_status } },
      {
        onSuccess: () => toast.success(`상태가 '${STATUS_LABELS[nextTrans.to_status]}'로 변경되었습니다`),
        onError: () => toast.error('상태 변경에 실패했습니다'),
      },
    )
  }

  const startEditStep = (step: TestStep) => {
    setEditingStepId(step.id)
    setAddingStep(false)
  }

  const cancelStepForm = () => {
    setAddingStep(false)
    setEditingStepId(null)
  }

  const handleSaveStep = (description: string, result: 'pass' | 'fail') => {
    if (!description.trim() || !run) return
    if (editingStepId) {
      updateStep.mutate(
        { id: editingStepId, payload: { description, result }, runId: run.id },
        {
          onSuccess: () => { cancelStepForm(); toast.success('단계가 수정되었습니다') },
          onError: () => toast.error('수정에 실패했습니다'),
        },
      )
    } else {
      createStep.mutate(
        { test_run_id: run.id, step_order: steps.length + 1, description, result },
        {
          onSuccess: () => { cancelStepForm(); toast.success('단계가 추가되었습니다') },
          onError: () => toast.error('추가에 실패했습니다'),
        },
      )
    }
  }

  const handleDeleteStep = () => {
    if (!deleteStepId || !run) return
    deleteStep.mutate(
      { id: deleteStepId, runId: run.id },
      {
        onSuccess: () => { setDeleteStepId(null); toast.success('단계가 삭제되었습니다') },
        onError: () => { setDeleteStepId(null); toast.error('삭제에 실패했습니다') },
      },
    )
  }

  return (
    <>
      <Sheet open={open} onOpenChange={onOpenChange}>
        <SheetContent side="right" className="sm:max-w-xl overflow-y-auto">
          {isLoading ? (
            <div className="flex items-center justify-center h-40">
              <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
            </div>
          ) : run ? (
            <>
              <SheetHeader className="pr-2">
                <div className="flex items-start justify-between gap-2">
                  <div className="space-y-0.5 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <SheetTitle className="text-xl font-bold">
                        {ctrl?.code ?? run.control_id.slice(0, 8) + '...'}
                      </SheetTitle>
                      <Badge variant="outline" className={STATUS_BADGE_CLASS[run.status]}>
                        {STATUS_LABELS[run.status]}
                      </Badge>
                    </div>
                    {ctrl && <p className="text-sm text-muted-foreground">{ctrl.name}</p>}
                  </div>
                  <Button
                    variant="outline"
                    size="sm"
                    className="shrink-0 mr-8"
                    disabled={isLocked}
                    onClick={() => setEditOpen(true)}
                  >
                    편집
                  </Button>
                </div>
              </SheetHeader>

              <div className="mt-4 space-y-1">
                {/* 섹션 1 — 기본 정보 */}
                <SectionTitle>기본 정보</SectionTitle>
                <Separator />
                <InfoRow label="회계연도" value={run.fiscal_year} />
                <InfoRow label="평가일" value={run.test_date?.slice(0, 10)} />
                <InfoRow label="샘플 수" value={run.sample_size} />
                <InfoRow
                  label="결과"
                  value={
                    run.result ? (
                      <Badge variant="outline" className={RESULT_BADGE_CLASS[run.result]}>
                        {RESULT_LABELS[run.result]}
                      </Badge>
                    ) : undefined
                  }
                />
                <InfoRow
                  label="평가 방법"
                  value={
                    <div className="flex flex-wrap gap-x-4 gap-y-1 mt-0.5">
                      {TEST_METHODS.map(({ key, label }) => {
                        const active = run[key] as boolean
                        return (
                          <span key={key} className="flex items-center gap-1 text-sm">
                            {active
                              ? <CheckCircle2 className="h-3.5 w-3.5 text-green-500" />
                              : <Circle className="h-3.5 w-3.5 text-muted-foreground/40" />
                            }
                            <span className={active ? '' : 'text-muted-foreground'}>{label}</span>
                          </span>
                        )
                      })}
                    </div>
                  }
                />

                {/* 섹션 2 — 워크플로 */}
                <SectionTitle>워크플로</SectionTitle>
                <Separator />
                <div className="py-2">
                  {nextTrans ? (
                    <Button size="sm" onClick={handleTransition} disabled={transition.isPending}>
                      {transition.isPending && (
                        <Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" />
                      )}
                      {nextTrans.label}
                    </Button>
                  ) : (
                    <span className="text-sm text-muted-foreground">최종 승인 완료</span>
                  )}
                </div>

                {/* 섹션 3 — 평가 단계 */}
                <SectionTitle>평가 단계</SectionTitle>
                <Separator />
                <div className="py-2 space-y-2">
                  {stepsLoading ? (
                    <div className="flex justify-center py-4">
                      <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
                    </div>
                  ) : (
                    <>
                      {steps.length === 0 && !addingStep && (
                        <p className="text-sm text-muted-foreground">등록된 단계 없음</p>
                      )}
                      {steps.map((step) => (
                        <div key={step.id} className="rounded-md border p-2.5">
                          {editingStepId === step.id ? (
                            <StepInlineForm
                              key={step.id}
                              initialDescription={step.description}
                              initialResult={step.result}
                              onSave={handleSaveStep}
                              onCancel={cancelStepForm}
                              isSaving={updateStep.isPending}
                            />
                          ) : (
                            <div className="flex items-start justify-between gap-2">
                              <div className="flex items-start gap-2 text-sm min-w-0">
                                <span className="text-muted-foreground shrink-0 w-4">{step.step_order}.</span>
                                <span className="break-words">{step.description}</span>
                              </div>
                              <div className="flex items-center gap-1 shrink-0">
                                <Badge variant="outline" className={`text-xs ${STEP_RESULT_CLASS[step.result]}`}>
                                  {STEP_RESULT_LABEL[step.result]}
                                </Badge>
                                <Button
                                  variant="ghost"
                                  size="icon"
                                  className="h-6 w-6"
                                  disabled={isLocked || !!editingStepId || addingStep}
                                  onClick={() => startEditStep(step)}
                                >
                                  <Pencil className="h-3 w-3" />
                                </Button>
                                <Button
                                  variant="ghost"
                                  size="icon"
                                  className="h-6 w-6 hover:bg-red-50 hover:text-red-600"
                                  disabled={isLocked || !!editingStepId || addingStep}
                                  onClick={() => setDeleteStepId(step.id)}
                                >
                                  <Trash2 className="h-3 w-3" />
                                </Button>
                              </div>
                            </div>
                          )}
                        </div>
                      ))}
                      {addingStep && (
                        <StepInlineForm
                          key="new"
                          initialDescription=""
                          initialResult="pass"
                          onSave={handleSaveStep}
                          onCancel={cancelStepForm}
                          isSaving={createStep.isPending}
                        />
                      )}
                      {!addingStep && !editingStepId && !isLocked && (
                        <Button
                          variant="outline"
                          size="sm"
                          className="w-full mt-1"
                          onClick={() => setAddingStep(true)}
                        >
                          + 단계 추가
                        </Button>
                      )}
                    </>
                  )}
                </div>

                {/* 섹션 4 — 상태 이력 */}
                <SectionTitle>상태 이력</SectionTitle>
                <Separator />
                <div className="py-2">
                  {(historyData?.items ?? []).length === 0 ? (
                    <p className="text-sm text-muted-foreground">이력 없음</p>
                  ) : (
                    <ol className="relative border-l border-muted-foreground/20 ml-2 space-y-4">
                      {[...(historyData?.items ?? [])].reverse().map((h) => (
                        <li key={h.id} className="ml-4">
                          <span className="absolute -left-1.5 mt-1 h-3 w-3 rounded-full border-2 border-background bg-muted-foreground/40" />
                          <div className="text-sm font-medium">
                            {h.from_status
                              ? `${STATUS_LABELS[h.from_status as TestRunStatus]} → `
                              : ''}
                            {STATUS_LABELS[h.to_status as TestRunStatus]}
                          </div>
                          <div className="text-xs text-muted-foreground mt-0.5">
                            {h.changed_by.display_name} · {h.changed_at.slice(0, 10)}
                          </div>
                          {h.reason && (
                            <div className="text-xs text-muted-foreground mt-0.5">{h.reason}</div>
                          )}
                        </li>
                      ))}
                    </ol>
                  )}
                </div>
              </div>
            </>
          ) : null}
        </SheetContent>
      </Sheet>

      {run && (
        <TestRunEditDialog run={run} open={editOpen} onOpenChange={setEditOpen} />
      )}

      <AlertDialog open={!!deleteStepId} onOpenChange={(o) => { if (!o) setDeleteStepId(null) }}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>이 단계를 삭제하시겠습니까?</AlertDialogTitle>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>취소</AlertDialogCancel>
            <AlertDialogAction
              className="bg-red-600 hover:bg-red-700"
              onClick={handleDeleteStep}
              disabled={deleteStep.isPending}
            >
              {deleteStep.isPending && <Loader2 className="h-3.5 w-3.5 mr-1 animate-spin" />}
              삭제
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  )
}
