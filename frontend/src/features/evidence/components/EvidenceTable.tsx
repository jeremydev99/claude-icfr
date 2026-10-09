import { useMemo, useState } from 'react'
import { useQueries } from '@tanstack/react-query'
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
import { formatDate } from '@/lib/utils'
import { downloadEvidenceFile, fetchCycleTargets } from '../api/evidenceApi'
import { useDeleteEvidenceFile } from '../api/useEvidence'
import type { EvidenceFile } from '../types'
import { queryKeys } from '@/lib/queryKeys'
import { useActiveTenantId } from '@/features/auth/store'
import { useCycles } from '@/features/schedule/api/useSchedule'
import { resolveEvidenceError } from '../evidence.pure'
import HelpButton from '@/features/help/HelpButton'

interface Props {
  files: EvidenceFile[]
  /** false 면 삭제 버튼을 숨긴다(조회 전용 사용자) */
  canDelete?: boolean
}

function formatSize(bytes: number): string {
  if (bytes >= 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(2)} MB`
  if (bytes >= 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${bytes} B`
}


export default function EvidenceTable({ files, canDelete = false }: Props) {
  const [downloadingId, setDownloadingId] = useState<string | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<EvidenceFile | null>(null)
  const [deleteError, setDeleteError] = useState<string | null>(null)
  const { mutate: deleteFile, isPending: isDeleting } = useDeleteEvidenceFile()

  // 회차명·통제 코드 표기 — 목록에 등장한 회차만 대상 스냅샷을 조회한다(업로드 다이얼로그와 캐시 공유)
  const tenantId = useActiveTenantId()
  const { data: cycles } = useCycles()
  const cycleName = useMemo(() => new Map((cycles ?? []).map((c) => [c.id, c.name])), [cycles])
  const cycleIds = useMemo(
    () => [...new Set(files.map((f) => f.cycle_id).filter((id): id is string => !!id))],
    [files],
  )
  const targetResults = useQueries({
    queries: cycleIds.map((id) => ({
      queryKey: queryKeys.evidence.cycleTargets(tenantId, id),
      queryFn: () => fetchCycleTargets(id),
      staleTime: 5 * 60_000,
    })),
  })
  const controlCode = new Map<string, string>()
  for (const r of targetResults) {
    for (const t of r.data ?? []) if (t.control_code) controlCode.set(t.control_id, t.control_code)
  }

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
    setDeleteError(null)
    deleteFile(deleteTarget.id, {
      onSuccess: () => setDeleteTarget(null),
      onError: (error) => setDeleteError(resolveEvidenceError(error, '삭제 중 오류가 발생했습니다.')),
    })
  }

  return (
    <>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>파일명</TableHead>
            <TableHead>회차</TableHead>
            <TableHead>통제</TableHead>
            <TableHead>크기</TableHead>
            <TableHead>업로드일</TableHead>
            <TableHead className="w-40 text-right"><HelpButton k="screen.evidence.files" /></TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {files.map((file) => (
            <TableRow key={file.id}>
              <TableCell className="font-medium">{file.filename}</TableCell>
              <TableCell>
                {file.cycle_id
                  ? (cycleName.get(file.cycle_id) ?? '—')
                  : <span className="text-muted-foreground">회차 없음(기존)</span>}
              </TableCell>
              <TableCell>
                {file.control_id ? (controlCode.get(file.control_id) ?? '—') : '—'}
              </TableCell>
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
                {canDelete && (
                  <Button
                    variant="destructive"
                    size="sm"
                    onClick={() => setDeleteTarget(file)}
                  >
                    삭제
                  </Button>
                )}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>

      <AlertDialog open={!!deleteTarget} onOpenChange={(v) => { if (!v) { setDeleteTarget(null); setDeleteError(null) } }}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>파일 삭제 확인</AlertDialogTitle>
            <AlertDialogDescription asChild>
              <div className="space-y-2">
                <p>선택한 파일을 삭제합니다.</p>
                {deleteTarget && (
                  <p className="font-medium text-foreground">{deleteTarget.filename}</p>
                )}
                <p className="text-muted-foreground">삭제 기록(삭제자·시각)은 남습니다.</p>
                {deleteError && <p className="text-destructive">{deleteError}</p>}
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
