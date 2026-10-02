import { useMemo, useRef, useState } from 'react'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { useCycles } from '@/features/schedule/api/useSchedule'
import { useCycleTargets, useUploadEvidenceFile } from '../api/useEvidence'
import { ALLOWED_EXTENSIONS } from '../types'
import {
  closedCycleNotice,
  cycleLabel,
  resolveEvidenceError,
  sortCyclesForUpload,
  validateFile,
} from '../evidence.pure'

interface Props {
  open: boolean
  onOpenChange: (open: boolean) => void
}

export default function EvidenceUploadDialog({ open, onOpenChange }: Props) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [cycleId, setCycleId] = useState<string | null>(null)
  const [controlId, setControlId] = useState<string | null>(null)
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [validationError, setValidationError] = useState<string | null>(null)
  const [serverError, setServerError] = useState<string | null>(null)

  const { data: cycleData, isLoading: cyclesLoading } = useCycles()
  const cycles = useMemo(() => sortCyclesForUpload(cycleData ?? []), [cycleData])
  const selectedCycle = cycles.find((c) => c.id === cycleId)
  const { data: targets, isLoading: targetsLoading } = useCycleTargets(cycleId)

  const { mutate: upload, isPending } = useUploadEvidenceFile()

  function handleCycleChange(id: string) {
    setCycleId(id)
    setControlId(null) // 대상 통제는 회차마다 다르다
    setServerError(null)
  }

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0] ?? null
    setServerError(null)
    if (!file) {
      setSelectedFile(null)
      setValidationError(null)
      return
    }
    setSelectedFile(file)
    setValidationError(validateFile(file))
  }

  function handleUpload() {
    if (!selectedFile || validationError || !cycleId || !controlId) return
    setServerError(null)
    upload(
      { file: selectedFile, cycleId, controlId },
      {
        onSuccess: () => handleClose(),
        onError: (error) => setServerError(resolveEvidenceError(error)),
      },
    )
  }

  function handleClose() {
    setCycleId(null)
    setControlId(null)
    setSelectedFile(null)
    setValidationError(null)
    setServerError(null)
    if (inputRef.current) inputRef.current.value = ''
    onOpenChange(false)
  }

  const noCycles = !cyclesLoading && cycles.length === 0
  const noTargets = !!cycleId && !targetsLoading && (targets?.length ?? 0) === 0
  const notice = closedCycleNotice(selectedCycle)
  const canUpload = !!cycleId && !!controlId && !!selectedFile && !validationError && !isPending

  return (
    <Dialog open={open} onOpenChange={(v) => { if (!v) handleClose() }}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>증빙 파일 업로드</DialogTitle>
          <DialogDescription>
            증빙은 평가 회차의 통제에 붙습니다. 회차와 통제를 고른 뒤 파일을 올려 주세요.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-2">
          {noCycles ? (
            <p className="text-sm text-muted-foreground">
              평가 회차가 없어 증빙을 올릴 수 없습니다. 평가자가 회차를 먼저 생성해야 합니다.
            </p>
          ) : (
            <>
              <div className="space-y-1">
                <Label>평가 회차</Label>
                <Select value={cycleId ?? ''} onValueChange={handleCycleChange} disabled={cyclesLoading}>
                  <SelectTrigger>
                    <SelectValue placeholder={cyclesLoading ? '불러오는 중...' : '회차 선택'} />
                  </SelectTrigger>
                  <SelectContent>
                    {cycles.map((c) => (
                      <SelectItem key={c.id} value={c.id}>{cycleLabel(c)}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                {notice && <p className="text-xs text-amber-600">{notice}</p>}
              </div>

              <div className="space-y-1">
                <Label>통제</Label>
                {noTargets ? (
                  <p className="text-sm text-muted-foreground">이 회차에는 대상 통제가 없습니다.</p>
                ) : (
                  <Select
                    value={controlId ?? ''}
                    onValueChange={(v) => { setControlId(v); setServerError(null) }}
                    disabled={!cycleId || targetsLoading}
                  >
                    <SelectTrigger>
                      <SelectValue
                        placeholder={!cycleId ? '회차를 먼저 선택' : targetsLoading ? '불러오는 중...' : '통제 선택'}
                      />
                    </SelectTrigger>
                    <SelectContent>
                      {(targets ?? []).map((t) => (
                        <SelectItem key={t.control_id} value={t.control_id}>
                          {t.control_code ?? t.control_id}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                )}
              </div>

              <div className="space-y-1">
                <Label htmlFor="evidence-file">파일</Label>
                <input
                  id="evidence-file"
                  ref={inputRef}
                  type="file"
                  accept={ALLOWED_EXTENSIONS.join(',')}
                  onChange={handleFileChange}
                  className="block w-full text-sm text-muted-foreground
                    file:mr-4 file:py-2 file:px-4
                    file:rounded-md file:border-0
                    file:text-sm file:font-medium
                    file:bg-primary file:text-primary-foreground
                    hover:file:bg-primary/90 cursor-pointer"
                />
                {selectedFile && !validationError && (
                  <p className="text-sm text-muted-foreground">
                    {selectedFile.name} ({(selectedFile.size / 1024 / 1024).toFixed(2)} MB)
                  </p>
                )}
                {validationError && <p className="text-sm text-destructive">{validationError}</p>}
                <p className="text-xs text-muted-foreground">
                  허용 형식: PDF, PNG, JPEG, XLSX, DOCX, HWP · 최대 50MB
                </p>
              </div>
            </>
          )}

          {serverError && <p className="text-sm text-destructive">{serverError}</p>}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={handleClose} disabled={isPending}>
            취소
          </Button>
          <Button onClick={handleUpload} disabled={!canUpload}>
            {isPending ? '업로드 중...' : '업로드'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
