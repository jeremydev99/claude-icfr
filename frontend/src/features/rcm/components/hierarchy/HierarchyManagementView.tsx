// RCM 신규 탭 — 상위 3계층(Process/SubProcess/Risk) CRUD.
// UsersPage.tsx의 사용자/역할 토글 패턴을 3-way로 확장.
import { useState } from 'react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import type { ProcessItem, SubProcessItem, RiskItem } from '../../types'
import {
  useProcessList,
  useDeleteProcess,
  useSubProcessList,
  useDeleteSubProcess,
  useRiskList,
  useDeleteRisk,
} from '../../api/useHierarchy'
import { extractHierarchyErrorMessage } from '../../api/errors'
import { canEditHierarchy } from '../../permissions'
import ProcessTable from './ProcessTable'
import SubProcessTable from './SubProcessTable'
import RiskTable from './RiskTable'
import ProcessFormDialog from './ProcessFormDialog'
import SubProcessFormDialog from './SubProcessFormDialog'
import RiskFormDialog from './RiskFormDialog'
import HierarchyDeleteConfirmDialog from './HierarchyDeleteConfirmDialog'

type HierarchyTab = 'process' | 'subProcess' | 'risk'

export default function HierarchyManagementView() {
  const [activeTab, setActiveTab] = useState<HierarchyTab>('process')
  const canEdit = canEditHierarchy()

  const { data: processData, isLoading: processLoading, isError: processError, error: processErr } = useProcessList()
  const { data: subProcessData, isLoading: subProcessLoading, isError: subProcessError, error: subProcessErr } = useSubProcessList()
  const { data: riskData, isLoading: riskLoading, isError: riskError, error: riskErr } = useRiskList()

  const processes = processData?.items ?? []
  const subProcesses = subProcessData?.items ?? []
  const risks = riskData?.items ?? []

  const deleteProcess = useDeleteProcess()
  const deleteSubProcess = useDeleteSubProcess()
  const deleteRisk = useDeleteRisk()

  // ── Process ────────────────────────────────────────────────
  const [processFormOpen, setProcessFormOpen] = useState(false)
  const [editProcess, setEditProcess] = useState<ProcessItem | null>(null)
  const [deleteProcessTarget, setDeleteProcessTarget] = useState<ProcessItem | null>(null)

  const handleDeleteProcessConfirm = async () => {
    if (!deleteProcessTarget) return
    try {
      await deleteProcess.mutateAsync(deleteProcessTarget.id)
      toast.success('프로세스가 삭제되었습니다')
      setDeleteProcessTarget(null)
    } catch (err) {
      toast.error(extractHierarchyErrorMessage(err))
    }
  }

  // ── SubProcess ─────────────────────────────────────────────
  const [subProcessFormOpen, setSubProcessFormOpen] = useState(false)
  const [editSubProcess, setEditSubProcess] = useState<SubProcessItem | null>(null)
  const [deleteSubProcessTarget, setDeleteSubProcessTarget] = useState<SubProcessItem | null>(null)

  const handleDeleteSubProcessConfirm = async () => {
    if (!deleteSubProcessTarget) return
    try {
      await deleteSubProcess.mutateAsync(deleteSubProcessTarget.id)
      toast.success('세부 프로세스가 삭제되었습니다')
      setDeleteSubProcessTarget(null)
    } catch (err) {
      toast.error(extractHierarchyErrorMessage(err))
    }
  }

  // ── Risk ───────────────────────────────────────────────────
  const [riskFormOpen, setRiskFormOpen] = useState(false)
  const [editRisk, setEditRisk] = useState<RiskItem | null>(null)
  const [deleteRiskTarget, setDeleteRiskTarget] = useState<RiskItem | null>(null)

  const handleDeleteRiskConfirm = async () => {
    if (!deleteRiskTarget) return
    try {
      await deleteRisk.mutateAsync(deleteRiskTarget.id)
      toast.success('위험이 삭제되었습니다')
      setDeleteRiskTarget(null)
    } catch (err) {
      toast.error(extractHierarchyErrorMessage(err))
    }
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-1 border rounded-md p-1 w-fit">
        <Button variant={activeTab === 'process' ? 'default' : 'ghost'} size="sm" onClick={() => setActiveTab('process')}>
          프로세스
        </Button>
        <Button variant={activeTab === 'subProcess' ? 'default' : 'ghost'} size="sm" onClick={() => setActiveTab('subProcess')}>
          세부 프로세스
        </Button>
        <Button variant={activeTab === 'risk' ? 'default' : 'ghost'} size="sm" onClick={() => setActiveTab('risk')}>
          위험
        </Button>
      </div>

      {activeTab === 'process' && (
        <div className="space-y-3">
          {canEdit && (
            <div className="flex justify-end">
              <Button size="sm" onClick={() => { setEditProcess(null); setProcessFormOpen(true) }}>
                + 프로세스 추가
              </Button>
            </div>
          )}
          <ProcessTable
            items={processes}
            isLoading={processLoading}
            isError={processError}
            error={processErr}
            onEditClick={(item) => { setEditProcess(item); setProcessFormOpen(true) }}
            onDeleteClick={setDeleteProcessTarget}
          />
        </div>
      )}

      {activeTab === 'subProcess' && (
        <div className="space-y-3">
          {canEdit && (
            <div className="flex justify-end">
              <Button size="sm" onClick={() => { setEditSubProcess(null); setSubProcessFormOpen(true) }}>
                + 세부 프로세스 추가
              </Button>
            </div>
          )}
          <SubProcessTable
            items={subProcesses}
            processes={processes}
            isLoading={subProcessLoading}
            isError={subProcessError}
            error={subProcessErr}
            onEditClick={(item) => { setEditSubProcess(item); setSubProcessFormOpen(true) }}
            onDeleteClick={setDeleteSubProcessTarget}
          />
        </div>
      )}

      {activeTab === 'risk' && (
        <div className="space-y-3">
          {canEdit && (
            <div className="flex justify-end">
              <Button size="sm" onClick={() => { setEditRisk(null); setRiskFormOpen(true) }}>
                + 위험 추가
              </Button>
            </div>
          )}
          <RiskTable
            items={risks}
            subProcesses={subProcesses}
            isLoading={riskLoading}
            isError={riskError}
            error={riskErr}
            onEditClick={(item) => { setEditRisk(item); setRiskFormOpen(true) }}
            onDeleteClick={setDeleteRiskTarget}
          />
        </div>
      )}

      <ProcessFormDialog
        open={processFormOpen}
        onOpenChange={(o) => { setProcessFormOpen(o); if (!o) setEditProcess(null) }}
        editTarget={editProcess}
      />
      <HierarchyDeleteConfirmDialog
        open={deleteProcessTarget !== null}
        target={deleteProcessTarget ? { label: `${deleteProcessTarget.code} — ${deleteProcessTarget.name}`, envelope: deleteProcessTarget.envelope } : null}
        itemTypeLabel="프로세스"
        onOpenChange={(open) => { if (!open) setDeleteProcessTarget(null) }}
        onConfirm={handleDeleteProcessConfirm}
        isPending={deleteProcess.isPending}
      />

      <SubProcessFormDialog
        open={subProcessFormOpen}
        onOpenChange={(o) => { setSubProcessFormOpen(o); if (!o) setEditSubProcess(null) }}
        editTarget={editSubProcess}
        processes={processes}
      />
      <HierarchyDeleteConfirmDialog
        open={deleteSubProcessTarget !== null}
        target={deleteSubProcessTarget ? { label: `${deleteSubProcessTarget.code} — ${deleteSubProcessTarget.name}`, envelope: deleteSubProcessTarget.envelope } : null}
        itemTypeLabel="세부 프로세스"
        onOpenChange={(open) => { if (!open) setDeleteSubProcessTarget(null) }}
        onConfirm={handleDeleteSubProcessConfirm}
        isPending={deleteSubProcess.isPending}
      />

      <RiskFormDialog
        open={riskFormOpen}
        onOpenChange={(o) => { setRiskFormOpen(o); if (!o) setEditRisk(null) }}
        editTarget={editRisk}
        subProcesses={subProcesses}
      />
      <HierarchyDeleteConfirmDialog
        open={deleteRiskTarget !== null}
        target={deleteRiskTarget ? { label: `${deleteRiskTarget.code} — ${deleteRiskTarget.description}`, envelope: deleteRiskTarget.envelope } : null}
        itemTypeLabel="위험"
        onOpenChange={(open) => { if (!open) setDeleteRiskTarget(null) }}
        onConfirm={handleDeleteRiskConfirm}
        isPending={deleteRisk.isPending}
      />
    </div>
  )
}
