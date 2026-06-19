import { useState } from 'react'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Button } from '@/components/ui/button'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import { downloadEvidenceFile } from '../api/evidenceApi'
import { useDeleteEvidenceFile } from '../api/useEvidence'
import type { EvidenceFile } from '../types'

interface Props {
  files: EvidenceFile[]
}

function formatSize(bytes: number): string {
  if (bytes >= 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(2)} MB`
  if (bytes >= 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${bytes} B`
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString('ko-KR', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  })
}

export default function EvidenceTable({ files }: Props) {
  const [downloadingId, setDownloadingId] = useState<string | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<EvidenceFile | null>(null)
  const { mutate: deleteFile, isPending: isDeleting } = useDeleteEvidenceFile()

  async function handleDownload(file: EvidenceFile) {
    setDownloadingId(file.id)
    try {
      const blob = await downloadEvidenceFile(file.id)
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = file.filename
      document.body.appendChild(a)
      a.click()
      a.remove()
      URL.revokeObjectURL(url)
    } finally {
      setDownloadingId(null)
    }
  }

  function handleDeleteConfirm() {
    if (!deleteTarget) return
    deleteFile(deleteTarget.id, {
      onSuccess: () => setDeleteTarget(null),
    })
  }

  return (
    <>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>파일명</TableHead>
            <TableHead>크기</TableHead>
            <TableHead>업로드일</TableHead>
            <TableHead className="text-right">액션</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {files.map((file) => (
            <TableRow key={file.id}>
              <TableCell className="font-medium">{file.filename}</TableCell>
              <TableCell>{formatSize(file.size_bytes)}</TableCell>
              <TableCell>{formatDate(file.created_at)}</TableCell>
              <TableCell className="text-right space-x-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => handleDownload(file)}
                  disabled={downloadingId === file.id}
                >
                  {downloadingId === file.id ? '다운로드 중...' : '다운로드'}
                </Button>
                <Button
                  variant="destructive"
                  size="sm"
                  onClick={() => setDeleteTarget(file)}
                >
                  삭제
                </Button>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>

      <AlertDialog open={!!deleteTarget} onOpenChange={(v) => { if (!v) setDeleteTarget(null) }}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>파일 삭제 확인</AlertDialogTitle>
            <AlertDialogDescription asChild>
              <div className="space-y-2">
                <p>정말 이 파일을 삭제하시겠습니까?</p>
                {deleteTarget && (
                  <p className="font-medium text-foreground">{deleteTarget.filename}</p>
                )}
                <p className="text-destructive">이 작업은 되돌릴 수 없습니다.</p>
              </div>
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={isDeleting}>취소</AlertDialogCancel>
            <AlertDialogAction
              onClick={(e) => { e.preventDefault(); handleDeleteConfirm() }}
              disabled={isDeleting}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {isDeleting ? '삭제 중...' : '삭제'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  )
}
