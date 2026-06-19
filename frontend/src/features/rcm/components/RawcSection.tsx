import { useState } from 'react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { useAuthStore } from '@/features/auth/store'
import { useRawcByControl, useCreateRawc, useUpdateRawc } from '../api/useRawc'
import {
  RAWC_SCORE_FIELDS,
  PRIOR_YEAR_LABELS,
  OVERALL_ASSESSMENT_LABELS,
} from '../types'
import type {
  ControlRiskAssessment,
  PriorYearEffectiveness,
  OverallAssessment,
} from '../types'

interface Props {
  controlId: string
  fiscalYear: number
}

type ScoreKey =
  | 'frequency_score'
  | 'nature_score'
  | 'precision_score'
  | 'dependency_score'
  | 'automation_score'
  | 'authority_score'
  | 'review_score'

interface FormState {
  frequency_score: number
  nature_score: number
  precision_score: number
  dependency_score: number
  automation_score: number
  authority_score: number
  review_score: number
  prior_year_effectiveness: PriorYearEffectiveness
  overall_assessment: OverallAssessment
}

const DEFAULT_FORM: FormState = {
  frequency_score: 2,
  nature_score: 2,
  precision_score: 2,
  dependency_score: 2,
  automation_score: 2,
  authority_score: 2,
  review_score: 2,
  prior_year_effectiveness: 'N/A',
  overall_assessment: 'Not_Higher',
}

function rawcToForm(rawc: ControlRiskAssessment): FormState {
  return {
    frequency_score: rawc.frequency_score,
    nature_score: rawc.nature_score,
    precision_score: rawc.precision_score,
    dependency_score: rawc.dependency_score,
    automation_score: rawc.automation_score,
    authority_score: rawc.authority_score,
    review_score: rawc.review_score,
    prior_year_effectiveness: rawc.prior_year_effectiveness,
    overall_assessment: rawc.overall_assessment,
  }
}

function ScoreButton({ value, selected, onClick }: { value: number; selected: boolean; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`w-8 h-8 rounded text-sm font-medium border transition-colors ${
        selected
          ? 'bg-primary text-primary-foreground border-primary'
          : 'bg-background text-foreground border-border hover:bg-muted'
      }`}
    >
      {value}
    </button>
  )
}

export default function RawcSection({ controlId, fiscalYear }: Props) {
  const user = useAuthStore((s) => s.user)
  const { data, isLoading } = useRawcByControl(controlId, fiscalYear)
  const createMutation = useCreateRawc()
  const updateMutation = useUpdateRawc()

  const existing = data?.items[0] ?? null
  const [editing, setEditing] = useState(false)
  const [form, setForm] = useState<FormState>(DEFAULT_FORM)

  const handleEditStart = () => {
    setForm(existing ? rawcToForm(existing) : DEFAULT_FORM)
    setEditing(true)
  }

  const handleCancel = () => setEditing(false)

  const handleScoreChange = (key: ScoreKey, value: number) => {
    setForm((prev) => ({ ...prev, [key]: value }))
  }

  const handleSave = async () => {
    const today = new Date().toISOString().slice(0, 10)
    try {
      if (existing) {
        await updateMutation.mutateAsync({
          id: existing.id,
          payload: { ...form, assessor_id: user?.id ?? null, assessment_date: today },
          controlId,
          fiscalYear,
        })
        toast.success('위험평가가 수정되었습니다')
      } else {
        await createMutation.mutateAsync({
          control_id: controlId,
          fiscal_year: fiscalYear,
          ...form,
          assessor_id: user?.id ?? null,
          assessment_date: today,
        })
        toast.success('위험평가가 저장되었습니다')
      }
      setEditing(false)
    } catch {
      toast.error('저장에 실패했습니다')
    }
  }

  const isPending = createMutation.isPending || updateMutation.isPending

  if (isLoading) {
    return <p className="text-sm text-muted-foreground py-2">불러오는 중...</p>
  }

  if (!editing && !existing) {
    return (
      <Button variant="outline" size="sm" className="mt-1" onClick={handleEditStart}>
        위험평가 입력
      </Button>
    )
  }

  if (!editing && existing) {
    return (
      <div className="space-y-1">
        <div className="grid grid-cols-2 gap-x-4 gap-y-1 py-1">
          {RAWC_SCORE_FIELDS.map(({ key, label }) => (
            <div key={key} className="flex items-center justify-between text-sm py-0.5">
              <span className="text-muted-foreground">{label}</span>
              <span className="font-medium">{existing[key]}</span>
            </div>
          ))}
        </div>
        <div className="grid grid-cols-[120px_1fr] gap-2 py-1 text-sm">
          <span className="text-muted-foreground">전기효과성</span>
          <span>{PRIOR_YEAR_LABELS[existing.prior_year_effectiveness]}</span>
        </div>
        <div className="grid grid-cols-[120px_1fr] gap-2 py-1 text-sm">
          <span className="text-muted-foreground">종합평가</span>
          <span>{OVERALL_ASSESSMENT_LABELS[existing.overall_assessment]}</span>
        </div>
        <div className="grid grid-cols-[120px_1fr] gap-2 py-1 text-sm">
          <span className="text-muted-foreground">평가일</span>
          <span>{existing.assessment_date ?? '—'}</span>
        </div>
        <Button variant="outline" size="sm" className="mt-2" onClick={handleEditStart}>
          편집
        </Button>
      </div>
    )
  }

  return (
    <div className="space-y-3 py-1">
      <div className="grid grid-cols-2 gap-x-6 gap-y-2">
        {RAWC_SCORE_FIELDS.map(({ key, label }) => (
          <div key={key} className="flex items-center justify-between text-sm">
            <span className="text-muted-foreground w-14 shrink-0">{label}</span>
            <div className="flex gap-1">
              {[1, 2, 3].map((v) => (
                <ScoreButton
                  key={v}
                  value={v}
                  selected={form[key as ScoreKey] === v}
                  onClick={() => handleScoreChange(key as ScoreKey, v)}
                />
              ))}
            </div>
          </div>
        ))}
      </div>

      <div className="flex items-center gap-2 text-sm">
        <span className="text-muted-foreground w-20 shrink-0">전기효과성</span>
        <Select
          value={form.prior_year_effectiveness}
          onValueChange={(v) => setForm((prev) => ({ ...prev, prior_year_effectiveness: v as PriorYearEffectiveness }))}
        >
          <SelectTrigger className="h-8 text-sm w-40">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {(Object.entries(PRIOR_YEAR_LABELS) as [PriorYearEffectiveness, string][]).map(([k, label]) => (
              <SelectItem key={k} value={k}>{label}</SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div className="flex items-center gap-2 text-sm">
        <span className="text-muted-foreground w-20 shrink-0">종합평가</span>
        <Select
          value={form.overall_assessment}
          onValueChange={(v) => setForm((prev) => ({ ...prev, overall_assessment: v as OverallAssessment }))}
        >
          <SelectTrigger className="h-8 text-sm w-40">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {(Object.entries(OVERALL_ASSESSMENT_LABELS) as [OverallAssessment, string][]).map(([k, label]) => (
              <SelectItem key={k} value={k}>{label}</SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div className="flex gap-2 pt-1">
        <Button size="sm" onClick={handleSave} disabled={isPending}>
          {isPending ? '저장 중...' : '저장'}
        </Button>
        <Button size="sm" variant="ghost" onClick={handleCancel} disabled={isPending}>
          취소
        </Button>
      </div>
    </div>
  )
}
