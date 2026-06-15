import { useState, useMemo } from 'react'
import { toast } from 'sonner'
import { useTestRuns } from '../api/useTestRuns'
import { useControls } from '@/features/rcm/api/useControls'
import TestRunSearchBar from '../components/TestRunSearchBar'
import TestRunTable from '../components/TestRunTable'
import CreateTestRunDialog from '../components/CreateTestRunDialog'
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
    <div className="p-6 space-y-4">
      <div>
        <h1 className="text-2xl font-semibold">평가 (Test)</h1>
        <p className="text-sm text-muted-foreground mt-1">
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
    </div>
  )
}
