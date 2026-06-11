import { useState } from 'react'
import { toast } from 'sonner'
import type { Control, ControlSearchParams } from '../types'
import { useControls } from '../api/useControls'
import ControlSearchBar from '../components/ControlSearchBar'
import ControlFilterChips from '../components/ControlFilterChips'
import ControlTable from '../components/ControlTable'
import ControlDetailSheet from '../components/ControlDetailSheet'
import ControlFormDialog from '../components/ControlFormDialog'
import ExcelUploadDialog from '../components/ExcelUploadDialog'

const DEFAULT_PARAMS: ControlSearchParams = {
  skip: 0,
  limit: 20,
  sort_by: 'code',
  sort_order: 'asc',
}

export default function RcmPage() {
  const [params, setParams] = useState<ControlSearchParams>(DEFAULT_PARAMS)
  const [selectedControl, setSelectedControl] = useState<Control | null>(null)
  const [sheetOpen, setSheetOpen] = useState(false)

  const [formOpen, setFormOpen] = useState(false)
  const [formMode, setFormMode] = useState<'create' | 'edit'>('create')
  const [editingControl, setEditingControl] = useState<Control | null>(null)

  const [uploadOpen, setUploadOpen] = useState(false)

  const { data, isLoading, isError, error, refetch } = useControls(params)

  const handleChange = (updated: Partial<ControlSearchParams>) => {
    setParams((prev) => ({ ...prev, ...updated }))
  }

  const handleReset = () => setParams(DEFAULT_PARAMS)

  const handleSelect = (control: Control) => {
    setSelectedControl(control)
    setSheetOpen(true)
  }

  const handleAddClick = () => {
    setFormMode('create')
    setEditingControl(null)
    setFormOpen(true)
  }

  const handleEditClick = (control: Control) => {
    setFormMode('edit')
    setEditingControl(control)
    setFormOpen(true)
  }

  const handleUploadSuccess = () => {
    setUploadOpen(false)
    toast.success('Excel 업로드가 완료되었습니다.')
    refetch()
  }

  return (
    <div className="p-6 space-y-4">
      <div>
        <h1 className="text-2xl font-semibold">RCM 관리</h1>
        <p className="text-sm text-muted-foreground mt-1">리스크-통제 매트릭스 관리</p>
      </div>

      <ControlSearchBar params={params} onChange={handleChange} onReset={handleReset} />
      <ControlFilterChips params={params} onChange={handleChange} />
      <ControlTable
        data={data}
        params={params}
        onParamsChange={handleChange}
        onSelect={handleSelect}
        onAddClick={handleAddClick}
        onEdit={handleEditClick}
        onUploadClick={() => setUploadOpen(true)}
        isLoading={isLoading}
        isError={isError}
        error={error}
      />

      <ControlDetailSheet
        control={selectedControl}
        open={sheetOpen}
        onOpenChange={setSheetOpen}
        onEditClick={handleEditClick}
      />

      <ControlFormDialog
        open={formOpen}
        onOpenChange={setFormOpen}
        mode={formMode}
        control={editingControl ?? undefined}
      />

      <ExcelUploadDialog
        open={uploadOpen}
        onOpenChange={setUploadOpen}
        onSuccess={handleUploadSuccess}
      />
    </div>
  )
}
