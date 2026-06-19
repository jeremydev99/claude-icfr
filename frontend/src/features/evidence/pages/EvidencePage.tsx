import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { useEvidenceFiles } from '../api/useEvidence'
import EvidenceTable from '../components/EvidenceTable'
import EvidenceUploadDialog from '../components/EvidenceUploadDialog'

export default function EvidencePage() {
  const [uploadOpen, setUploadOpen] = useState(false)
  const { data, isLoading, isError } = useEvidenceFiles()

  const files = data?.items ?? []

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">증빙 관리</h1>
        <Button onClick={() => setUploadOpen(true)}>파일 업로드</Button>
      </div>

      {isLoading && (
        <p className="text-muted-foreground text-sm">불러오는 중...</p>
      )}

      {isError && (
        <p className="text-destructive text-sm">파일 목록을 불러오지 못했습니다.</p>
      )}

      {!isLoading && !isError && files.length === 0 && (
        <p className="text-muted-foreground text-sm">
          업로드된 증빙 파일이 없습니다. 파일 업로드 버튼을 눌러 추가하세요.
        </p>
      )}

      {files.length > 0 && <EvidenceTable files={files} />}

      <EvidenceUploadDialog open={uploadOpen} onOpenChange={setUploadOpen} />
    </div>
  )
}
