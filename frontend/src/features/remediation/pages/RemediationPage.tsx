import { useState } from 'react'
import { toast } from 'sonner'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import { Button } from '@/components/ui/button'
import { Loader2 } from 'lucide-react'
import { useDeficiencies, useDeleteDeficiency } from '../api/useDeficiencies'
import { usePlans } from '../api/useRemediationPlans'
import DeficiencyTable from '../components/DeficiencyTable'
import DeficiencyFormDialog from '../components/DeficiencyFormDialog'
import RemediationPlanCreateDialog from '../components/RemediationPlanCreateDialog'
import RemediationPlanDetailSheet from '../components/RemediationPlanDetailSheet'
import type { Deficiency } from '../types'

export default function RemediationPage() {
  const { data: deficiencyData, isLoading: defLoading, isError: defError, error: defErr } =
    useDeficiencies({ skip: 0, limit: 100 })
  const { data: planData } = usePlans({ skip: 0, limit: 1000 })
  const deleteDeficiency = useDeleteDeficiency()

  // ── 미비점 상태 ──────────────────────────────────────────
  const [defFormOpen, setDefFormOpen] = useState(false)
  const [editTarget, setEditTarget] = useState<Deficiency | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<Deficiency | null>(null)

  const handleEditClick = (item: Deficiency) => {
    setEditTarget(item)
    setDefFormOpen(true)
  }

  const handleDeleteConfirm = async () => {
    if (!deleteTarget) return
    try {
      await deleteDeficiency.mutateAsync(deleteTarget.id)
      toast.success('미비점이 삭제되었습니다')
    } catch {
      toast.error('삭제에 실패했습니다')
    } finally {
      setDeleteTarget(null)
    }
  }

  // ── 개선계획 상태 ────────────────────────────────────────
  const [selectedPlanId, setSelectedPlanId] = useState<string | null>(null)
  const [planDetailOpen, setPlanDetailOpen] = useState(false)

  const [planCreateOpen, setPlanCreateOpen] = useState(false)
  const [prefilledDeficiencyId, setPrefilledDeficiencyId] = useState<string | undefined>()

  const handlePlanClick = (planId: string) => {
    setSelectedPlanId(planId)
    setPlanDetailOpen(true)
  }

  const handleCreatePlanClick = (deficiencyId: string) => {
    setPrefilledDeficiencyId(deficiencyId)
    setPlanCreateOpen(true)
  }

  return (
    <div className="p-6 space-y-4">
      <div>
        <h1 className="text-2xl font-semibold">개선계획 (Remediation)</h1>
        <p className="text-sm text-muted-foreground mt-1">
          미비점 등록·심각도 평가·개선계획 수립·워크플로 관리
        </p>
      </div>

      <div className="flex justify-end">
        <Button
          size="sm"
          onClick={() => { setEditTarget(null); setDefFormOpen(true) }}
        >
          + 미비점 등록
        </Button>
      </div>

      <DeficiencyTable
        data={deficiencyData}
        plans={planData?.items ?? []}
        onAddClick={() => { setEditTarget(null); setDefFormOpen(true) }}
        onEditClick={handleEditClick}
        onDeleteClick={(item) => setDeleteTarget(item)}
        onPlanClick={handlePlanClick}
        onCreatePlanClick={handleCreatePlanClick}
        isLoading={defLoading}
        isError={defError}
        error={defErr}
      />

      {/* Dialogs / Sheets */}
      <DeficiencyFormDialog
        open={defFormOpen}
        onOpenChange={(o) => { setDefFormOpen(o); if (!o) setEditTarget(null) }}
        editTarget={editTarget}
      />

      <AlertDialog open={!!deleteTarget} onOpenChange={(o) => { if (!o) setDeleteTarget(null) }}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>미비점 [{deleteTarget?.code}]을 삭제하시겠습니까?</AlertDialogTitle>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>취소</AlertDialogCancel>
            <AlertDialogAction
              className="bg-red-600 hover:bg-red-700"
              onClick={handleDeleteConfirm}
              disabled={deleteDeficiency.isPending}
            >
              {deleteDeficiency.isPending && <Loader2 className="h-3.5 w-3.5 mr-1 animate-spin" />}
              삭제
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <RemediationPlanCreateDialog
        open={planCreateOpen}
        onOpenChange={(o) => { setPlanCreateOpen(o); if (!o) setPrefilledDeficiencyId(undefined) }}
        prefilledDeficiencyId={prefilledDeficiencyId}
        onSuccess={() => {
          setPlanCreateOpen(false)
          setPrefilledDeficiencyId(undefined)
          toast.success('개선계획이 등록되었습니다')
        }}
      />

      <RemediationPlanDetailSheet
        planId={selectedPlanId}
        open={planDetailOpen}
        onOpenChange={setPlanDetailOpen}
      />
    </div>
  )
}
