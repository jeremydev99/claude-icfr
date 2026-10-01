import { useEffect, useMemo, useState } from 'react'
import { toast } from 'sonner'
import { AlertTriangle, Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Textarea } from '@/components/ui/textarea'
import { ASSIGNMENT_ROLES, ASSIGNMENT_SCOPES, isConflictReasonRequired } from '../PolicyDefs.pure'
import { errorDetail, useCreateAssignment, type TargetItem } from '../api/PolicyAssignmentApi'

interface Props {
  open: boolean
  onOpenChange: (open: boolean) => void
  processes: TargetItem[]
  controls: TargetItem[]
  users: { id: string; display_name: string }[]
}

export default function AssignmentAddDialog({ open, onOpenChange, processes, controls, users }: Props) {
  const [scope, setScope] = useState<string>('control')
  const [targetQuery, setTargetQuery] = useState('')
  const [targetId, setTargetId] = useState('')
  const [role, setRole] = useState<string>('control_owner')
  const [userId, setUserId] = useState('')
  const [reason, setReason] = useState('')
  const [conflictMsg, setConflictMsg] = useState<string | null>(null)
  const create = useCreateAssignment()

  useEffect(() => {
    if (open) {
      setScope('control')
      setTargetQuery('')
      setTargetId('')
      setRole('control_owner')
      setUserId('')
      setReason('')
      setConflictMsg(null)
    }
  }, [open])

  const targets = scope === 'process' ? processes : controls
  const filteredTargets = useMemo(() => {
    const q = targetQuery.trim().toLowerCase()
    const list = q
      ? targets.filter((t) => `${t.code} ${t.name}`.toLowerCase().includes(q))
      : targets
    return list.slice(0, 200)
  }, [targets, targetQuery])

  const canSubmit = !!targetId && !!role && !!userId && (!conflictMsg || reason.trim().length > 0)

  const submit = async () => {
    try {
      await create.mutateAsync({
        scope,
        target_id: targetId,
        role_name: role,
        user_id: userId,
        conflict_reason: reason.trim() || null,
      })
      toast.success(conflictMsg ? '겸직 사유와 함께 배정했습니다' : '배정했습니다')
      onOpenChange(false)
    } catch (e) {
      const detail = errorDetail(e, '배정하지 못했습니다')
      const status = (e as { response?: { status?: number } })?.response?.status
      if (status === 409 && isConflictReasonRequired(detail)) {
        // 경고형 409 — 사유를 받으면 저장할 수 있다
        setConflictMsg(detail)
        return
      }
      toast.error(detail)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>역할 배정 추가</DialogTitle>
          <DialogDescription>
            같은 대상·역할에 이미 배정이 있으면 담당자만 교체됩니다. 프로세스 배정은 소속 통제의 기본값이며,
            통제 배정이 있으면 그것이 우선합니다.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <Label>범위</Label>
              <Select
                value={scope}
                onValueChange={(v) => {
                  setScope(v)
                  setTargetId('')
                  setConflictMsg(null)
                }}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {ASSIGNMENT_SCOPES.map((s) => (
                    <SelectItem key={s.value} value={s.value}>
                      {s.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1">
              <Label>역할</Label>
              <Select
                value={role}
                onValueChange={(v) => {
                  setRole(v)
                  setConflictMsg(null)
                }}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {ASSIGNMENT_ROLES.map((r) => (
                    <SelectItem key={r.value} value={r.value}>
                      {r.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          <div className="space-y-1">
            <Label>대상 {scope === 'process' ? '프로세스' : '통제'}</Label>
            <Input
              placeholder="코드·이름 검색"
              value={targetQuery}
              onChange={(e) => setTargetQuery(e.target.value)}
            />
            <Select
              value={targetId}
              onValueChange={(v) => {
                setTargetId(v)
                setConflictMsg(null)
              }}
            >
              <SelectTrigger>
                <SelectValue placeholder={`선택 (${filteredTargets.length}건)`} />
              </SelectTrigger>
              <SelectContent className="max-h-72">
                {filteredTargets.map((t) => (
                  <SelectItem key={t.id} value={t.id}>
                    {t.code} · {t.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-1">
            <Label>담당자</Label>
            <Select
              value={userId}
              onValueChange={(v) => {
                setUserId(v)
                setConflictMsg(null)
              }}
            >
              <SelectTrigger>
                <SelectValue placeholder="선택" />
              </SelectTrigger>
              <SelectContent className="max-h-72">
                {users.map((u) => (
                  <SelectItem key={u.id} value={u.id}>
                    {u.display_name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {conflictMsg && (
            <div className="space-y-2 rounded-md border border-amber-300 bg-amber-50 p-3 text-sm dark:border-amber-700 dark:bg-amber-950/40">
              <p className="flex items-start gap-2 text-amber-800 dark:text-amber-200">
                <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
                {conflictMsg}
              </p>
              <Label htmlFor="conflict-reason">겸직 사유 (이력으로 남습니다)</Label>
              <Textarea
                id="conflict-reason"
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                placeholder="예: 소규모 조직으로 대체 인력 없음 — 상위 검토로 보완"
              />
            </div>
          )}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            취소
          </Button>
          <Button onClick={submit} disabled={!canSubmit || create.isPending}>
            {create.isPending && <Loader2 className="mr-1 h-4 w-4 animate-spin" />}
            {conflictMsg ? '사유와 함께 저장' : '저장'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
