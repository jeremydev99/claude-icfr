import { useState, useMemo } from 'react'
import { toast } from 'sonner'
import { useTestRuns } from '../api/useTestRuns'
import { useControls } from '@/features/rcm/api/useControls'
import TestRunSearchBar from '../components/TestRunSearchBar'
import TestRunTable from '../components/TestRunTable'
import CreateTestRunDialog from '../components/CreateTestRunDialog'
import TestRunDetailSheet from '../components/TestRunDetailSheet'
import type { TestRunSearchParams } from '../types'
import type { Control } from '@/features/rcm/types'

const currentYear = new Date().getFullYear()

const DEFAULT_PARAMS: TestRunSearchParams = {
  fiscal_year: currentYear,
  skip: 0,
  limit: 20,
}

export default function TestPage() {
  const [searchParams, setSearchParams] = useState<TestRunSearchParams>(DEFAULT_PARAMS)
  const [createOpen, setCreateOpen] = useState(false)
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null)
  const [detailOpen, setDetailOpen] = useState(false)

  const { data, isLoading, isError, error } = useTestRuns(searchParams)

  // control_code / control_name 매핑용 — 전체 목록 한 번 조회
  const { data: controlsData } = useControls({
    skip: 0,
    limit: 200,
    sort_by: 'code',
    sort_order: 'asc',
  })

  const controlMap = useMemo((): Record<string, Control> => {
    if (!controlsData?.items) return {}
    return Object.fromEntries(controlsData.items.map((c) => [c.id, c]))
  }, [controlsData])

  const handleParamsChange = (updated: Partial<TestRunSearchParams>) => {
    setSearchParams((prev) => ({ ...prev, ...updated }))
  }

  return (
    <div className="mx-auto max-w-[1400px] space-y-6 p-6 md:p-8">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">평가 (Test)</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          통제별 운영평가 계획·실행·결과 관리
        </p>
      </div>

      <TestRunSearchBar
        value={searchParams}
        onChange={handleParamsChange}
        onAddClick={() => setCreateOpen(true)}
      />

      <TestRunTable
        data={data}
        controlMap={controlMap}
        params={searchParams}
        onParamsChange={handleParamsChange}
        onAddClick={() => setCreateOpen(true)}
        onRowClick={(id) => { setSelectedRunId(id); setDetailOpen(true) }}
        isLoading={isLoading}
        isError={isError}
        error={error}
      />

      <CreateTestRunDialog
        open={createOpen}
        onOpenChange={setCreateOpen}
        defaultFiscalYear={searchParams.fiscal_year ?? currentYear}
        onSuccess={() => {
          setCreateOpen(false)
          toast.success('평가가 추가되었습니다')
        }}
      />

      <TestRunDetailSheet
        runId={selectedRunId}
        open={detailOpen}
        onOpenChange={setDetailOpen}
        controlMap={controlMap}
      />
    </div>
  )
}
