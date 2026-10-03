import EmptyState from '@/components/illustration/EmptyState'
import { useState } from 'react'
import { Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { useEvidenceFiles } from '../api/useEvidence'
import EvidenceTable from '../components/EvidenceTable'
import EvidenceUploadDialog from '../components/EvidenceUploadDialog'

export default function EvidencePage() {
  const [uploadOpen, setUploadOpen] = useState(false)
  const { data, isLoading, isError } = useEvidenceFiles()

  const files = data?.items ?? []

  return (
    <div className="mx-auto max-w-[1400px] space-y-6 p-6 md:p-8">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold tracking-tight">증빙 관리</h1>
        <Button onClick={() => setUploadOpen(true)}>파일 업로드</Button>
      </div>

      {isLoading && (
        <div className="flex items-center justify-center p-12 text-muted-foreground gap-2">
          <Loader2 className="h-5 w-5 animate-spin" />
          불러오는 중...
        </div>
      )}

      {isError && (
        <p className="text-destructive text-sm">파일 목록을 불러오지 못했습니다.</p>
      )}

      {!isLoading && !isError && files.length === 0 && (
        <EmptyState
          slot="empty-upload"
          title="업로드된 증빙 파일이 없습니다"
          description="파일 업로드 버튼을 눌러 추가하세요."
          action={<Button size="sm" onClick={() => setUploadOpen(true)}>파일 업로드</Button>}
        />
      )}

      {files.length > 0 && <EvidenceTable files={files} />}

      <EvidenceUploadDialog open={uploadOpen} onOpenChange={setUploadOpen} />
    </div>
  )
}
