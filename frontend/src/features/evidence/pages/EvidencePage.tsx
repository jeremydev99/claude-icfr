import EmptyState from '@/components/illustration/EmptyState'
import { useMemo, useState } from 'react'
import { Loader2 } from 'lucide-react'
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
import { useCanWrite } from '@/features/auth/useCanWrite'
import { useCycleTargets, useEvidenceFiles } from '../api/useEvidence'
import { buildFileFilterParams, cycleLabel, FILTER_ALL, sortCyclesForUpload } from '../evidence.pure'
import EvidenceTable from '../components/EvidenceTable'
import EvidenceUploadDialog from '../components/EvidenceUploadDialog'

export default function EvidencePage() {
  const [uploadOpen, setUploadOpen] = useState(false)
  // 조회 전용 사용자(external_auditor)에게는 업로드·삭제 버튼을 숨긴다 — 최종 강제는 서버 403(13.9-74 ③)
  const canWrite = useCanWrite()
  // 목록 필터(회차 → 통제) — 화면 상태만, 새로고침 시 초기화(13.9-74 ②)
  const [cycleFilter, setCycleFilter] = useState(FILTER_ALL)
  const [controlFilter, setControlFilter] = useState(FILTER_ALL)
  const { data: cycleData } = useCycles()
  const cycles = useMemo(() => sortCyclesForUpload(cycleData ?? []), [cycleData])
  const { data: targets } = useCycleTargets(cycleFilter === FILTER_ALL ? null : cycleFilter)
  const filtered = cycleFilter !== FILTER_ALL
  const { data, isLoading, isError } = useEvidenceFiles(buildFileFilterParams(cycleFilter, controlFilter))

  const files = data?.items ?? []

  return (
    <div className="mx-auto max-w-[1400px] space-y-6 p-6 md:p-8">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold tracking-tight">증빙 관리</h1>
        {canWrite && <Button onClick={() => setUploadOpen(true)}>파일 업로드</Button>}
      </div>

      <div className="flex flex-wrap items-end gap-3">
        <div className="space-y-1">
          <Label>평가 회차</Label>
          <Select value={cycleFilter} onValueChange={(v) => { setCycleFilter(v); setControlFilter(FILTER_ALL) }}>
            <SelectTrigger className="w-72"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value={FILTER_ALL}>전체 회차</SelectItem>
              {cycles.map((c) => (
                <SelectItem key={c.id} value={c.id}>{cycleLabel(c)}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-1">
          <Label>통제</Label>
          <Select value={controlFilter} onValueChange={setControlFilter} disabled={!filtered}>
            <SelectTrigger className="w-56">
              <SelectValue placeholder="회차를 먼저 선택" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={FILTER_ALL}>{filtered ? '전체 통제' : '회차를 먼저 선택'}</SelectItem>
              {(targets ?? []).map((t) => (
                <SelectItem key={t.control_id} value={t.control_id}>{t.control_code ?? t.control_id}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        {filtered && (
          <Button variant="ghost" size="sm" onClick={() => { setCycleFilter(FILTER_ALL); setControlFilter(FILTER_ALL) }}>
            필터 해제
          </Button>
        )}
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

      {!isLoading && !isError && files.length === 0 && filtered && (
        <p className="text-sm text-muted-foreground">조건에 맞는 증빙 파일이 없습니다.</p>
      )}

      {!isLoading && !isError && files.length === 0 && !filtered && (
        <EmptyState
          slot="empty-upload"
          title="업로드된 증빙 파일이 없습니다"
          description={canWrite ? '파일 업로드 버튼을 눌러 추가하세요.' : undefined}
          action={canWrite ? <Button size="sm" onClick={() => setUploadOpen(true)}>파일 업로드</Button> : undefined}
        />
      )}

      {files.length > 0 && <EvidenceTable files={files} canDelete={canWrite} />}

      {canWrite && <EvidenceUploadDialog open={uploadOpen} onOpenChange={setUploadOpen} />}
    </div>
  )
}
