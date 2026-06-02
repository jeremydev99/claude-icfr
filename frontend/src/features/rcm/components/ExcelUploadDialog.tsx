import { useRef, useState } from 'react'
import { Upload, FileSpreadsheet, AlertTriangle, X } from 'lucide-react'
import { isAxiosError } from 'axios'

function extractErrorMessage(err: unknown): string {
  if (isAxiosError(err)) {
    const detail = err.response?.data?.detail
    if (typeof detail === 'string') return detail
    if (err.response?.status === 401) return '로그인이 필요합니다'
    if (err.response?.status === 422) return '파일 형식 또는 요청이 올바르지 않습니다'
    if (err.response?.status === 500) return '서버 오류가 발생했습니다'
    if (!err.response) return '서버에 연결할 수 없습니다. 백엔드가 실행 중인지 확인하세요'
  }
  return '알 수 없는 오류가 발생했습니다'
}
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import ExcelPreviewTable from './ExcelPreviewTable'
import {
  previewExcel,
  commitExcel,
  type ExcelPreviewResponse,
  type ExcelCommitResponse,
} from '../api/uploadExcel'

type Step = 'select' | 'previewing' | 'preview' | 'committing' | 'done' | 'error'

interface Props {
  open: boolean
  onOpenChange: (open: boolean) => void
  onSuccess?: () => void
}

export default function ExcelUploadDialog({ open, onOpenChange, onSuccess }: Props) {
  const [step, setStep] = useState<Step>('select')
  const [file, setFile] = useState<File | null>(null)
  const [previewData, setPreviewData] = useState<ExcelPreviewResponse | null>(null)
  const [commitData, setCommitData] = useState<ExcelCommitResponse | null>(null)
  const [errorMsg, setErrorMsg] = useState<string>('')
  const [isDragging, setIsDragging] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  const reset = () => {
    setStep('select')
    setFile(null)
    setPreviewData(null)
    setCommitData(null)
    setErrorMsg('')
  }

  const handleClose = () => {
    reset()
    onOpenChange(false)
  }

  const handleFileSelect = (selected: File | null) => {
    if (!selected) return
    if (!selected.name.endsWith('.xlsx')) {
      setErrorMsg('.xlsx 파일만 허용됩니다')
      setStep('error')
      return
    }
    setFile(selected)
    setErrorMsg('')
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(false)
    handleFileSelect(e.dataTransfer.files[0] ?? null)
  }

  const handlePreview = async () => {
    if (!file) return
    setStep('previewing')
    try {
      const data = await previewExcel(file)
      setPreviewData(data)
      setStep('preview')
    } catch (err) {
      setErrorMsg(extractErrorMessage(err))
      setStep('error')
    }
  }

  const handleCommit = async () => {
    if (!file) return
    setStep('committing')
    try {
      const data = await commitExcel(file)
      setCommitData(data)
      setStep('done')
    } catch (err) {
      setErrorMsg(extractErrorMessage(err))
      setStep('error')
    }
  }

  const handleDone = () => {
    reset()
    onOpenChange(false)
    onSuccess?.()
  }

  return (
    <Dialog open={open} onOpenChange={(v) => { if (!v) handleClose() }}>
      <DialogContent className="max-w-4xl max-h-[90vh] flex flex-col gap-0 p-0">
        <DialogHeader className="px-6 pt-6 pb-3">
          <DialogTitle>RCM Excel 업로드</DialogTitle>
        </DialogHeader>

        <div className="flex-1 overflow-y-auto px-6 pb-2 space-y-4">
          {/* ── STEP: select ── */}
          {step === 'select' && (
            <>
              <div className="rounded-md border border-yellow-300 bg-yellow-50 px-4 py-3 text-sm text-yellow-800 flex gap-2">
                <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5" />
                <span>
                  안내: Excel 업로드는 실제 백엔드 DB에 저장됩니다.
                  현재 화면에 보이는 통제 목록(mock 데이터)과는 별도로 저장되며, 추후 목록도 실제 API로 전환 예정입니다.
                </span>
              </div>

              <div
                className={`flex flex-col items-center justify-center gap-3 rounded-lg border-2 border-dashed p-10 transition-colors cursor-pointer
                  ${isDragging ? 'border-primary bg-primary/5' : 'border-muted-foreground/30 hover:border-primary/50'}`}
                onDragOver={(e) => { e.preventDefault(); setIsDragging(true) }}
                onDragLeave={() => setIsDragging(false)}
                onDrop={handleDrop}
                onClick={() => inputRef.current?.click()}
              >
                <FileSpreadsheet className="h-12 w-12 text-muted-foreground/50" />
                {file ? (
                  <div className="text-center" onClick={(e) => e.stopPropagation()}>
                    <div className="flex items-center gap-2 justify-center">
                      <p className="font-medium text-sm">{file.name}</p>
                      <button
                        aria-label="선택 취소"
                        onClick={() => { setFile(null); if (inputRef.current) inputRef.current.value = '' }}
                        className="ml-3 rounded-full bg-gray-100 p-1 text-gray-500 hover:bg-red-100 hover:text-red-600 transition-colors cursor-pointer"
                      >
                        <X className="h-4 w-4" />
                      </button>
                    </div>
                    <p className="text-xs text-muted-foreground mt-1">{(file.size / 1024).toFixed(1)} KB</p>
                  </div>
                ) : (
                  <div className="text-center">
                    <p className="text-sm font-medium">파일을 드래그하거나 클릭해서 선택하세요</p>
                    <p className="text-xs text-muted-foreground mt-1">지원 형식: .xlsx (사이냅소프트 RCM 양식)</p>
                  </div>
                )}
                <input
                  ref={inputRef}
                  type="file"
                  accept=".xlsx"
                  className="hidden"
                  onChange={(e) => handleFileSelect(e.target.files?.[0] ?? null)}
                />
              </div>
            </>
          )}

          {/* ── STEP: previewing ── */}
          {step === 'previewing' && (
            <div className="flex flex-col items-center justify-center gap-3 py-16">
              <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
              <p className="text-sm text-muted-foreground">Excel 분석 중...</p>
              <p className="text-xs text-muted-foreground">100건 이상은 잠시 걸릴 수 있습니다</p>
            </div>
          )}

          {/* ── STEP: preview ── */}
          {step === 'preview' && previewData && (
            <>
              <div className="grid grid-cols-4 gap-3">
                <SummaryCard label="전체" value={previewData.summary.total_rows} color="default" />
                <SummaryCard label="저장 가능" value={previewData.summary.valid_rows} color="green" />
                <SummaryCard label="오류" value={previewData.summary.errors.length} color="red" />
                <SummaryCard label="경고" value={previewData.summary.warnings.length} color="yellow" />
              </div>

              <div>
                <p className="text-sm font-medium mb-2">
                  미리보기 (최대 20건 표시 — 유효 항목만)
                </p>
                <ExcelPreviewTable items={previewData.preview} />
              </div>

              {previewData.summary.errors.length > 0 && (
                <div className="rounded-md border border-red-200 bg-red-50 p-3">
                  <p className="text-sm font-medium text-red-700 mb-1">파싱 오류 ({previewData.summary.errors.length}건)</p>
                  <ul className="space-y-0.5">
                    {previewData.summary.errors.map((e, i) => (
                      <li key={i} className="text-xs text-red-600">{e}</li>
                    ))}
                  </ul>
                </div>
              )}

              {previewData.summary.warnings.length > 0 && (
                <div className="rounded-md border border-yellow-200 bg-yellow-50 p-3">
                  <p className="text-sm font-medium text-yellow-700 mb-1">경고 ({previewData.summary.warnings.length}건) — 기본값으로 저장됩니다</p>
                  <ul className="space-y-0.5">
                    {previewData.summary.warnings.map((w, i) => (
                      <li key={i} className="text-xs text-yellow-700">{w}</li>
                    ))}
                  </ul>
                </div>
              )}
            </>
          )}

          {/* ── STEP: committing ── */}
          {step === 'committing' && (
            <div className="flex flex-col items-center justify-center gap-3 py-16">
              <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
              <p className="text-sm text-muted-foreground">
                저장 중... ({previewData?.summary.valid_rows ?? 0}건)
              </p>
            </div>
          )}

          {/* ── STEP: done ── */}
          {step === 'done' && commitData && (
            <div className="space-y-3">
              <div className="rounded-md border border-green-200 bg-green-50 p-4">
                <p className="font-medium text-green-800 mb-3">저장 완료</p>
                <div className="grid grid-cols-2 gap-2 text-sm text-green-700">
                  <span>통제 저장:</span>
                  <span className="font-medium">{commitData.created.controls}건</span>
                  <span>프로세스 처리:</span>
                  <span className="font-medium">{commitData.created.processes}건</span>
                  <span>세부 프로세스 처리:</span>
                  <span className="font-medium">{commitData.created.sub_processes}건</span>
                  <span>위험 처리:</span>
                  <span className="font-medium">{commitData.created.risks}건</span>
                  <span>어서션 처리:</span>
                  <span className="font-medium">{commitData.created.assertions}건</span>
                </div>
              </div>
              {commitData.summary.errors.length > 0 && (
                <p className="text-xs text-muted-foreground">
                  파싱 오류 {commitData.summary.errors.length}건은 건너뛰었습니다.
                </p>
              )}
            </div>
          )}

          {/* ── STEP: error ── */}
          {step === 'error' && (
            <div className="rounded-md border border-red-200 bg-red-50 p-4">
              <p className="font-medium text-red-700 mb-1">오류 발생</p>
              <p className="text-sm text-red-600">{errorMsg || '알 수 없는 오류가 발생했습니다.'}</p>
            </div>
          )}
        </div>

        <DialogFooter className="px-6 py-4 border-t">
          {step === 'select' && (
            <>
              <Button variant="outline" onClick={handleClose}>닫기</Button>
              <Button onClick={handlePreview} disabled={!file}>
                <Upload className="h-4 w-4 mr-1.5" />
                미리보기
              </Button>
            </>
          )}
          {(step === 'previewing' || step === 'committing') && (
            <Button variant="outline" disabled>취소</Button>
          )}
          {step === 'preview' && previewData && (
            <>
              <Button variant="outline" onClick={reset}>처음으로</Button>
              <Button
                onClick={handleCommit}
                disabled={previewData.summary.valid_rows === 0}
              >
                등록 ({previewData.summary.valid_rows}건)
              </Button>
            </>
          )}
          {step === 'done' && (
            <Button onClick={handleDone}>확인</Button>
          )}
          {step === 'error' && (
            <>
              <Button variant="outline" onClick={handleClose}>닫기</Button>
              <Button onClick={reset}>다시 시도</Button>
            </>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function SummaryCard({
  label, value, color,
}: {
  label: string
  value: number
  color: 'default' | 'green' | 'red' | 'yellow'
}) {
  const cls = {
    default: 'bg-muted/50 border-muted',
    green: 'bg-green-50 border-green-200 text-green-700',
    red: 'bg-red-50 border-red-200 text-red-700',
    yellow: 'bg-yellow-50 border-yellow-200 text-yellow-700',
  }[color]

  return (
    <div className={`rounded-lg border p-3 text-center ${cls}`}>
      <p className="text-2xl font-bold">{value}</p>
      <p className="text-xs mt-0.5">{label}</p>
    </div>
  )
}
