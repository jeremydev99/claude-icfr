import { useState } from 'react'
import { isAxiosError } from 'axios'
import { toast } from 'sonner'
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
import { ChevronDown } from 'lucide-react'
import ControlSelector from './ControlSelector'
import { useCreateTestRun } from '../api/useTestRuns'
import type { Control } from '@/features/rcm/types'

interface Props {
  open: boolean
  onOpenChange: (open: boolean) => void
  defaultFiscalYear: number
  onSuccess: () => void
}

function extractErrorMessage(err: unknown, fiscalYear: number): string {
  if (isAxiosError(err)) {
    const status = err.response?.status
    const data = err.response?.data
    if (status === 409) {
      return `해당 통제의 ${fiscalYear}년 평가가 이미 존재합니다. 기존 평가를 수정하거나 다른 연도를 선택해주세요.`
    }
    if (status === 422) {
      if (Array.isArray(data?.detail)) {
        return data.detail.map((d: { msg: string }) => d.msg).join(', ')
      }
      return '입력값을 확인해주세요'
    }
    if (typeof data?.detail === 'string') return data.detail
    if (!err.response) return '서버에 연결할 수 없습니다'
  }
  return '알 수 없는 오류가 발생했습니다'
}

export default function CreateTestRunDialog({ open, onOpenChange, defaultFiscalYear, onSuccess }: Props) {
  const [selectedControl, setSelectedControl] = useState<Control | null>(null)
  const [fiscalYear, setFiscalYear] = useState(defaultFiscalYear)
  const [selectorOpen, setSelectorOpen] = useState(false)

  const createMutation = useCreateTestRun()

  const handleOpenChange = (next: boolean) => {
    if (!next) {
      setSelectedControl(null)
      setFiscalYear(defaultFiscalYear)
    }
    onOpenChange(next)
  }

  const handleSubmit = async () => {
    if (!selectedControl) {
      toast.error('통제를 선택해주세요')
      return
    }
    if (!fiscalYear || fiscalYear < 2000 || fiscalYear > 2100) {
      toast.error('올바른 평가 연도를 입력해주세요')
      return
    }
    try {
      await createMutation.mutateAsync({
        control_id: selectedControl.id,
        fiscal_year: fiscalYear,
      })
      onSuccess()
    } catch (err) {
      toast.error(extractErrorMessage(err, fiscalYear))
    }
  }

  return (
    <>
      <Dialog open={open} onOpenChange={handleOpenChange}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>평가 추가</DialogTitle>
          </DialogHeader>

          <div className="space-y-4 py-2">
            <div className="space-y-1.5">
              <Label>
                통제 <span className="text-destructive">*</span>
              </Label>
              <button
                type="button"
                onClick={() => setSelectorOpen(true)}
                className="flex w-full items-center justify-between rounded-md border px-3 py-2 text-sm hover:bg-accent transition-colors"
              >
                {selectedControl ? (
                  <span>
                    {selectedControl.code} — {selectedControl.name}
                  </span>
                ) : (
                  <span className="text-muted-foreground">통제를 선택하세요...</span>
                )}
                <ChevronDown className="h-4 w-4 text-muted-foreground" />
              </button>
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="fiscal-year">
                평가 연도 <span className="text-destructive">*</span>
              </Label>
              <Input
                id="fiscal-year"
                type="number"
                value={fiscalYear}
                onChange={(e) => setFiscalYear(Number(e.target.value))}
                min={2000}
                max={2100}
              />
            </div>

            <div className="rounded-md bg-muted/50 px-3 py-2 text-sm text-muted-foreground">
              ⓘ 평가는 <strong>계획(planned)</strong> 상태로 생성됩니다. 세부 절차·결과는 상세 화면에서 입력하세요 (다음 업데이트 예정).
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => handleOpenChange(false)}>
              취소
            </Button>
            <Button onClick={handleSubmit} disabled={createMutation.isPending}>
              {createMutation.isPending ? '추가 중...' : '추가'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <ControlSelector
        open={selectorOpen}
        onOpenChange={setSelectorOpen}
        onSelect={(ctrl) => setSelectedControl(ctrl)}
      />
    </>
  )
}
