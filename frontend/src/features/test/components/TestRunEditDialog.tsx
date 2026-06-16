import { useState, useEffect } from 'react'
import { Loader2 } from 'lucide-react'
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Checkbox } from '@/components/ui/checkbox'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { toast } from 'sonner'
import { useUpdateTestRun } from '../api/useTestRuns'
import { RESULT_LABELS, type TestRun, type TestResult, type TestRunUpdatePayload } from '../types'

interface Props {
  run: TestRun
  open: boolean
  onOpenChange: (open: boolean) => void
}

type MethodKey = 'method_inspection' | 'method_reperformance' | 'method_observation' | 'method_inquiry'

const METHODS: { key: MethodKey; label: string }[] = [
  { key: 'method_inspection', label: '검사' },
  { key: 'method_reperformance', label: '재수행' },
  { key: 'method_observation', label: '관찰' },
  { key: 'method_inquiry', label: '질문' },
]

export default function TestRunEditDialog({ run, open, onOpenChange }: Props) {
  const updateRun = useUpdateTestRun()

  const [form, setForm] = useState<TestRunUpdatePayload>({
    test_date: run.test_date?.slice(0, 10) ?? null,
    result: run.result ?? null,
    sample_size: run.sample_size ?? null,
    method_inspection: run.method_inspection,
    method_reperformance: run.method_reperformance,
    method_observation: run.method_observation,
    method_inquiry: run.method_inquiry,
  })

  useEffect(() => {
    setForm({
      test_date: run.test_date?.slice(0, 10) ?? null,
      result: run.result ?? null,
      sample_size: run.sample_size ?? null,
      method_inspection: run.method_inspection,
      method_reperformance: run.method_reperformance,
      method_observation: run.method_observation,
      method_inquiry: run.method_inquiry,
    })
  }, [run])

  const handleSave = () => {
    updateRun.mutate(
      { id: run.id, payload: form },
      {
        onSuccess: () => {
          toast.success('평가 정보가 수정되었습니다')
          onOpenChange(false)
        },
        onError: () => toast.error('수정에 실패했습니다'),
      },
    )
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>평가 편집</DialogTitle>
        </DialogHeader>

        <div className="space-y-4 py-2">
          <div className="space-y-1.5">
            <Label>평가일</Label>
            <Input
              type="date"
              value={form.test_date ?? ''}
              onChange={(e) =>
                setForm((f) => ({ ...f, test_date: e.target.value || null }))
              }
            />
          </div>

          <div className="space-y-1.5">
            <Label>결과</Label>
            <Select
              value={form.result ?? '__none__'}
              onValueChange={(v) =>
                setForm((f) => ({ ...f, result: v === '__none__' ? null : (v as TestResult) }))
              }
            >
              <SelectTrigger>
                <SelectValue placeholder="결과 선택" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="__none__">—</SelectItem>
                {(Object.entries(RESULT_LABELS) as [TestResult, string][]).map(([v, label]) => (
                  <SelectItem key={v} value={v}>{label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-1.5">
            <Label>샘플 수</Label>
            <Input
              type="number"
              min={0}
              value={form.sample_size ?? ''}
              onChange={(e) =>
                setForm((f) => ({
                  ...f,
                  sample_size: e.target.value ? Number(e.target.value) : null,
                }))
              }
            />
          </div>

          <div className="space-y-2">
            <Label>평가 방법</Label>
            <div className="grid grid-cols-2 gap-2">
              {METHODS.map(({ key, label }) => (
                <div key={key} className="flex items-center gap-2">
                  <Checkbox
                    id={key}
                    checked={!!form[key]}
                    onCheckedChange={(checked) =>
                      setForm((f) => ({ ...f, [key]: !!checked }))
                    }
                  />
                  <label htmlFor={key} className="text-sm cursor-pointer">
                    {label}
                  </label>
                </div>
              ))}
            </div>
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            취소
          </Button>
          <Button onClick={handleSave} disabled={updateRun.isPending}>
            {updateRun.isPending && (
              <Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" />
            )}
            저장
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
