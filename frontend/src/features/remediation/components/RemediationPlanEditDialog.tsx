import { useEffect, useState } from 'react'
import { isAxiosError } from 'axios'
import { toast } from 'sonner'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { useAuthStore } from '@/features/auth/store'
import { isIcfrStaffForUser } from '@/features/auth/permissions.pure'
import { useUsers } from '@/features/users/api/useUsers'
import { useUpdatePlan } from '../api/useRemediationPlans'
import type { RemediationPlan, RemediationPlanUpdatePayload, RemediationPriority } from '../types'

function errText(err: unknown): string {
  if (isAxiosError(err)) {
    const d = err.response?.data?.detail
    if (typeof d === 'string') return d
    if (Array.isArray(d)) return d.map((x: { msg: string }) => x.msg).join(', ')
  }
  return '저장하지 못했습니다'
}

type Form = {
  owner_id: string
  target_date: string
  priority: RemediationPriority
  action_plan: string
  improvement_description: string
  owner_opinion: string
  reviewer_opinion: string
}

const OPTIONAL: (keyof Form)[] = ['improvement_description', 'owner_opinion', 'reviewer_opinion']

function fromPlan(plan: RemediationPlan): Form {
  return {
    owner_id: plan.owner_id,
    target_date: plan.target_date?.slice(0, 10) ?? '',
    priority: plan.priority as RemediationPriority,
    action_plan: plan.action_plan ?? '',
    improvement_description: plan.improvement_description ?? '',
    owner_opinion: plan.owner_opinion ?? '',
    reviewer_opinion: plan.reviewer_opinion ?? '',
  }
}

/**
 * 개선계획 수정(13.9-126) — 승인 전까지. 바뀐 칸만 보낸다(서버 exclude_unset).
 * 선택 칸은 비우면 지워지고, 담당자·목표일·개선 조치는 필수. 검토자 의견은 내부회계 관리자만(서버도 403).
 */
export default function RemediationPlanEditDialog({ plan, open, onOpenChange }: {
  plan: RemediationPlan
  open: boolean
  onOpenChange: (v: boolean) => void
}) {
  const user = useAuthStore((s) => s.user)
  const isStaff = isIcfrStaffForUser(user)
  const update = useUpdatePlan()
  const { data: usersData } = useUsers({ limit: 200 })
  const users = (usersData?.items ?? []).filter((u) => u.is_active || u.id === plan.owner_id)
  const [form, setForm] = useState<Form>(() => fromPlan(plan))
  useEffect(() => {
    if (open) setForm(fromPlan(plan))
  }, [open, plan])
  const set = <K extends keyof Form>(k: K, v: Form[K]) => setForm((f) => ({ ...f, [k]: v }))

  const save = async () => {
    if (!form.owner_id || !form.target_date || !form.action_plan.trim()) {
      toast.error('담당자·목표일·개선 조치는 비울 수 없습니다')
      return
    }
    const before = fromPlan(plan)
    const payload: Record<string, unknown> = {}
    for (const k of Object.keys(form) as (keyof Form)[]) {
      if (form[k] === before[k]) continue
      if (k === 'reviewer_opinion' && !isStaff) continue
      const v = String(form[k]).trim()
      payload[k] = OPTIONAL.includes(k) ? v || null : v
    }
    if (Object.keys(payload).length === 0) {
      onOpenChange(false)
      return
    }
    try {
      await update.mutateAsync({ id: plan.id, payload: payload as RemediationPlanUpdatePayload })
      toast.success('개선계획을 수정했습니다')
      onOpenChange(false)
    } catch (e) {
      toast.error(errText(e))
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] max-w-xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle>개선계획 수정</DialogTitle>
          <DialogDescription>승인 전까지 수정할 수 있습니다. 수정 내역은 감사 로그에 남습니다.</DialogDescription>
        </DialogHeader>
        <div className="space-y-4 py-2">
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label>담당자 <span className="text-destructive">*</span></Label>
              <Select value={form.owner_id} onValueChange={(v) => set('owner_id', v)}>
                <SelectTrigger><SelectValue placeholder="담당자 선택" /></SelectTrigger>
                <SelectContent>
                  {users.map((u) => <SelectItem key={u.id} value={u.id}>{u.display_name}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="edit_target_date">목표일 <span className="text-destructive">*</span></Label>
              <Input id="edit_target_date" type="date" value={form.target_date}
                onChange={(e) => set('target_date', e.target.value)} />
            </div>
          </div>
          <div className="space-y-1.5">
            <Label>우선순위</Label>
            <Select value={form.priority} onValueChange={(v) => set('priority', v as RemediationPriority)}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="High">상 (High)</SelectItem>
                <SelectItem value="Medium">중 (Medium)</SelectItem>
                <SelectItem value="Low">하 (Low)</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="edit_action_plan">개선 조치 <span className="text-destructive">*</span></Label>
            <Textarea id="edit_action_plan" rows={3} value={form.action_plan}
              onChange={(e) => set('action_plan', e.target.value)} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="edit_improvement">개선 내용</Label>
            <Textarea id="edit_improvement" rows={3} value={form.improvement_description}
              onChange={(e) => set('improvement_description', e.target.value)} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="edit_owner_opinion">담당자 의견</Label>
            <Textarea id="edit_owner_opinion" rows={2} value={form.owner_opinion}
              onChange={(e) => set('owner_opinion', e.target.value)} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="edit_reviewer_opinion">
              검토자 의견{' '}
              {!isStaff && <span className="text-xs font-normal text-muted-foreground">— 내부회계 관리자만 입력</span>}
            </Label>
            <Textarea id="edit_reviewer_opinion" rows={2} value={form.reviewer_opinion} disabled={!isStaff}
              onChange={(e) => set('reviewer_opinion', e.target.value)} />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>취소</Button>
          <Button onClick={save} disabled={update.isPending}>저장</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
