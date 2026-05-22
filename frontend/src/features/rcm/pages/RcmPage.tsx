import { useState } from 'react'
import type { ControlSearchParams } from '../types'
import { useControls } from '../api/useControls'
import ControlSearchBar from '../components/ControlSearchBar'
import ControlFilterChips from '../components/ControlFilterChips'
import ControlTable from '../components/ControlTable'

const DEFAULT_PARAMS: ControlSearchParams = {
  skip: 0,
  limit: 20,
  sort_by: 'code',
  sort_order: 'asc',
}

export default function RcmPage() {
  const [params, setParams] = useState<ControlSearchParams>(DEFAULT_PARAMS)
  const { data } = useControls(params)

  const handleChange = (updated: Partial<ControlSearchParams>) => {
    setParams((prev) => ({ ...prev, ...updated }))
  }

  const handleReset = () => setParams(DEFAULT_PARAMS)

  return (
    <div className="p-6 space-y-4">
      <div>
        <h1 className="text-2xl font-semibold">RCM 관리</h1>
        <p className="text-sm text-muted-foreground mt-1">리스크-통제 매트릭스 관리</p>
      </div>

      <ControlSearchBar params={params} onChange={handleChange} onReset={handleReset} />
      <ControlFilterChips params={params} onChange={handleChange} />
      <ControlTable data={data} params={params} onParamsChange={handleChange} />
    </div>
  )
}
