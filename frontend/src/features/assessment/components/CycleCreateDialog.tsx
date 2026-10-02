import { useEffect, useState } from 'react'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { FREQ_LABEL, KIND_LABEL } from '@/features/schedule/schedule.pure'
import { resolveEvidenceError as resolveServerError } from '@/features/evidence/evidence.pure'
import { useCreateCycle, useCyclePeriodSuggestion } from '../api/cycleApi'
import {
  CYCLE_FREQUENCIES,
  CYCLE_KINDS,
  createdNotice,
  periodIndexOptions,
  periodLabel,
  suggestCycleName,
} from '../cycle.pure'

interface Props {
  open: boolean
  onOpenChange: (open: boolean) => void
  /** 화면에서 보고 있는 회계연도 — 그 연도의 회차를 만드는 경우가 대부분이다 */
  fiscalYear: number
  /** 올해 회계연도. 이 연도면 차수 기본값을 "지금 차수"로 서버에서 받는다 */
  currentFiscalYear: number
}

export default function CycleCreateDialog({ open, onOpenChange, fiscalYear, currentFiscalYear }: Props) {
  const [kind, setKind] = useState<string>('operation')
  const [frequency, setFrequency] = useState<string>('quarterly')
  const [fy, setFy] = useState(fiscalYear)
  // null = 서버가 정하는 "지금 차수"(올해일 때만). 받은 뒤 값으로 고정한다
  const [periodIndex, setPeriodIndex] = useState<number | null>(null)
  const [name, setName] = useState('')
  const [nameTouched, setNameTouched] = useState(false)
  const [periodStart, setPeriodStart] = useState('')
  const [periodEnd, setPeriodEnd] = useState('')
  const [dueDate, setDueDate] = useState('')
  const [serverError, setServerError] = useState<string | null>(null)
  const [notice, setNotice] = useState<ReturnType<typeof createdNotice> | null>(null)

  const effectiveIndex = periodIndex ?? (fy === currentFiscalYear ? null : 1)
  const { data: suggestion } = useCyclePeriodSuggestion(frequency, fy, effectiveIndex ?? 0)
  const create = useCreateCycle()

  useEffect(() => {
    if (open) {
      setFy(fiscalYear)
      setPeriodIndex(null)
    }
  }, [open, fiscalYear])

  // 제안값 반영 — 기간은 제안이 바뀔 때마다 덮어쓴다(주기·차수를 바꿨다는 것은 기간을 다시 잡겠다는 뜻).
  // 회차명은 사용자가 직접 고쳤으면 건드리지 않는다.
  useEffect(() => {
    if (!suggestion) return
    if (periodIndex === null) setPeriodIndex(suggestion.period_index)
    setPeriodStart(suggestion.period_start)
    setPeriodEnd(suggestion.period_end)
    if (!nameTouched) {
      setName(suggestCycleName(fy, kind, frequency, suggestion.period_index, suggestion.period_start))
    }
  }, [suggestion]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!nameTouched && suggestion) {
      setName(suggestCycleName(fy, kind, frequency, suggestion.period_index, suggestion.period_start))
    }
  }, [kind]) // eslint-disable-line react-hooks/exhaustive-deps

  function reset() {
    setKind('operation')
    setFrequency('quarterly')
    setPeriodIndex(null)
    setName('')
    setNameTouched(false)
    setDueDate('')
    setServerError(null)
    setNotice(null)
  }

  function handleClose() {
    reset()
    onOpenChange(false)
  }

  function handleSubmit() {
    if (!canSubmit || effectiveIndex === null) return
    setServerError(null)
    create.mutate(
      {
        kind,
        frequency,
        name: name.trim(),
        fiscal_year: fy,
        period_index: effectiveIndex,
        period_start: periodStart,
        period_end: periodEnd,
        due_date: dueDate || null,
      },
      {
        onSuccess: (cycle) => setNotice(createdNotice(cycle.target_count)),
        onError: (e) => setServerError(resolveServerError(e, '회차 생성 중 오류가 발생했습니다.')),
      },
    )
  }

  const periodError = periodStart && periodEnd && periodEnd < periodStart ? '종료일이 시작일보다 빠릅니다.' : null
  const canSubmit =
    !!name.trim() && !!periodStart && !!periodEnd && !periodError && effectiveIndex !== null && !create.isPending

  return (
    <Dialog open={open} onOpenChange={(v) => { if (!v) handleClose() }}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>평가 회차 생성</DialogTitle>
          <DialogDescription>
            주기를 고르면 같은 평가주기의 통제가 대상으로 자동 고정됩니다. 회차는 평가자(전담부서)만 만들 수 있습니다.
          </DialogDescription>
        </DialogHeader>

        {notice ? (
          <p className={notice.tone === 'warn' ? 'text-sm text-amber-600' : 'text-sm'}>{notice.text}</p>
        ) : (
          <div className="grid grid-cols-2 gap-3 py-2">
            <div className="space-y-1">
              <Label>종류</Label>
              <Select value={kind} onValueChange={setKind}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  {CYCLE_KINDS.map((k) => <SelectItem key={k} value={k}>{KIND_LABEL[k]}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1">
              <Label>주기</Label>
              <Select value={frequency} onValueChange={(v) => { setFrequency(v); setPeriodIndex(fy === currentFiscalYear ? null : 1) }}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  {CYCLE_FREQUENCIES.map((f) => <SelectItem key={f} value={f}>{FREQ_LABEL[f]}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1">
              <Label htmlFor="cycle-fy">회계연도</Label>
              <Input
                id="cycle-fy"
                type="number"
                value={fy}
                onChange={(e) => {
                  const v = Number(e.target.value)
                  if (Number.isInteger(v) && v >= 2000 && v <= 2100) {
                    setFy(v)
                    setPeriodIndex(v === currentFiscalYear ? null : 1)
                  }
                }}
              />
            </div>
            <div className="space-y-1">
              <Label>차수</Label>
              <Select
                value={effectiveIndex === null ? '' : String(effectiveIndex)}
                onValueChange={(v) => setPeriodIndex(Number(v))}
                disabled={frequency === 'annual'}
              >
                <SelectTrigger><SelectValue placeholder="불러오는 중..." /></SelectTrigger>
                <SelectContent>
                  {periodIndexOptions(frequency).map((i) => (
                    <SelectItem key={i} value={String(i)}>
                      {periodLabel(frequency, i, i === effectiveIndex ? periodStart : null)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="col-span-2 space-y-1">
              <Label htmlFor="cycle-name">회차명</Label>
              <Input
                id="cycle-name"
                value={name}
                maxLength={200}
                onChange={(e) => { setName(e.target.value); setNameTouched(true) }}
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="cycle-start">평가 시작일</Label>
              <Input id="cycle-start" type="date" value={periodStart} onChange={(e) => setPeriodStart(e.target.value)} />
            </div>
            <div className="space-y-1">
              <Label htmlFor="cycle-end">평가 종료일</Label>
              <Input id="cycle-end" type="date" value={periodEnd} onChange={(e) => setPeriodEnd(e.target.value)} />
            </div>
            <div className="space-y-1">
              <Label htmlFor="cycle-due">작업 기한 (선택)</Label>
              <Input id="cycle-due" type="date" value={dueDate} onChange={(e) => setDueDate(e.target.value)} />
            </div>
            <p className="col-span-2 text-xs text-muted-foreground">
              기간은 회계연도 시작월 기준 제안값입니다. 필요하면 조정하세요.
            </p>
            {periodError && <p className="col-span-2 text-sm text-destructive">{periodError}</p>}
            {serverError && <p className="col-span-2 text-sm text-destructive">{serverError}</p>}
          </div>
        )}

        <DialogFooter>
          {notice ? (
            <Button onClick={handleClose}>닫기</Button>
          ) : (
            <>
              <Button variant="outline" onClick={handleClose} disabled={create.isPending}>취소</Button>
              <Button onClick={handleSubmit} disabled={!canSubmit}>
                {create.isPending ? '생성 중...' : '생성'}
              </Button>
            </>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
