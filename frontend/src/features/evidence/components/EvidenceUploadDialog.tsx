import { useRef, useState } from 'react'
import axios from 'axios'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { useUploadEvidenceFile } from '../api/useEvidence'
import { ALLOWED_EXTENSIONS, ALLOWED_MIME_TYPES, MAX_FILE_SIZE_BYTES } from '../types'

interface Props {
  open: boolean
  onOpenChange: (open: boolean) => void
}

function validateFile(file: File): string | null {
  if (file.size > MAX_FILE_SIZE_BYTES) {
    return `파일 크기(${(file.size / 1024 / 1024).toFixed(1)}MB)가 50MB를 초과합니다.`
  }
  const ext = '.' + file.name.split('.').pop()?.toLowerCase()
  const mimeOk = (ALLOWED_MIME_TYPES as readonly string[]).includes(file.type)
  const extOk = ALLOWED_EXTENSIONS.includes(ext)
  if (!mimeOk && !extOk) {
    return `허용되지 않는 파일 형식입니다. (${ALLOWED_EXTENSIONS.join(', ')})`
  }
  return null
}

export default function EvidenceUploadDialog({ open, onOpenChange }: Props) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [validationError, setValidationError] = useState<string | null>(null)
  const [serverError, setServerError] = useState<string | null>(null)

  const { mutate: upload, isPending } = useUploadEvidenceFile()

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0] ?? null
    setServerError(null)
    if (!file) {
      setSelectedFile(null)
      setValidationError(null)
      return
    }
    const err = validateFile(file)
    setSelectedFile(file)
    setValidationError(err)
  }

  function handleUpload() {
    if (!selectedFile || validationError) return
    setServerError(null)
    upload(selectedFile, {
      onSuccess: () => {
        handleClose()
      },
      onError: (error) => {
        if (axios.isAxiosError(error)) {
          const status = error.response?.status
          if (status === 413) {
            setServerError('파일 크기가 서버 허용 한도를 초과했습니다.')
          } else if (status === 415) {
            setServerError('허용되지 않는 파일 형식입니다.')
          } else {
            setServerError('업로드 중 오류가 발생했습니다.')
          }
        } else {
          setServerError('업로드 중 오류가 발생했습니다.')
        }
      },
    })
  }

  function handleClose() {
    setSelectedFile(null)
    setValidationError(null)
    setServerError(null)
    if (inputRef.current) inputRef.current.value = ''
    onOpenChange(false)
  }

  const canUpload = !!selectedFile && !validationError && !isPending

  return (
    <Dialog open={open} onOpenChange={(v) => { if (!v) handleClose() }}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>증빙 파일 업로드</DialogTitle>
        </DialogHeader>

        <div className="space-y-3 py-2">
          <input
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

          {validationError && (
            <p className="text-sm text-destructive">{validationError}</p>
          )}

          {serverError && (
            <p className="text-sm text-destructive">{serverError}</p>
          )}

          <p className="text-xs text-muted-foreground">
            허용 형식: PDF, PNG, JPEG, XLSX, DOCX, HWP · 최대 50MB
          </p>
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
