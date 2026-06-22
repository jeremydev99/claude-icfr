import { useState } from 'react'
import { isAxiosError } from 'axios'
import { toast } from 'sonner'
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { useCreatePlan } from '../api/useRemediationPlans'
import { useDeficiencies } from '../api/useDeficiencies'
import type { RemediationPriority } from '../types'
import { useUsers } from '@/features/users/api/useUsers'

interface Props {
  open: boolean
  onOpenChange: (open: boolean) => void
  onSuccess: () => void
}

function extractErrorMessage(err: unknown): string {
  if (isAxiosError(err)) {
    const data = err.response?.data
    const status = err.response?.status
    if (status === 422) {
      if (Array.isArray(data?.detail)) {
        return data.detail.map((d: { msg: string }) => d.msg).join(', ')
      }
      return '입력값을 확인해주세요'
    }
    if (typeof data?.detail === 'string') return data.detail
    if (!err.response) return '서버에 연결할 수 없습니다'
  }
  return '알 수 없는 오류가 발생했습니다'
}

const defaultForm = {
  deficiency_id: '',
  owner_id: '',
  target_date: '',
  action_plan: '',
  priority: 'Medium' as RemediationPriority,
}

export default function RemediationPlanCreateDialog({ open, onOpenChange, onSuccess }: Props) {
  const [form, setForm] = useState(defaultForm)

  const createMutation = useCreatePlan()
  const { data: usersData } = useUsers({ limit: 100 })
  const { data: deficienciesData } = useDeficiencies({ limit: 100 })

  const activeUsers = (usersData?.items ?? []).filter((u) => u.is_active)
  const openDeficiencies = (deficienciesData?.items ?? []).filter(
    (d) => d.status === 'open' || d.status === 'in_progress'
  )

  const handleOpenChange = (next: boolean) => {
    if (!next) setForm(defaultForm)
    onOpenChange(next)
  }

  const handleSubmit = async () => {
    if (!form.deficiency_id.trim()) { toast.error('미비점을 선택하세요'); return }
    if (!form.owner_id.trim()) { toast.error('담당자를 선택하세요'); return }
    if (!form.target_date) { toast.error('목표일을 입력하세요'); return }
    if (!form.action_plan.trim()) { toast.error('개선 조치 내용을 입력하세요'); return }

    try {
      await createMutation.mutateAsync({
        deficiency_id: form.deficiency_id.trim(),
        owner_id: form.owner_id.trim(),
        target_date: form.target_date,
        action_plan: form.action_plan.trim(),
        priority: form.priority,
      })
      onSuccess()
    } catch (err) {
      toast.error(extractErrorMessage(err))
    }
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="max-w-xl">
        <DialogHeader>
          <DialogTitle>개선계획 등록</DialogTitle>
        </DialogHeader>

        <div className="space-y-4 py-2">
          <div className="space-y-1.5">
            <Label>
              미비점 <span className="text-destructive">*</span>
            </Label>
            <Select
              value={form.deficiency_id}
              onValueChange={(v) => setForm((f) => ({ ...f, deficiency_id: v }))}
            >
              <SelectTrigger>
                <SelectValue placeholder="미비점 선택..." />
              </SelectTrigger>
              <SelectContent>
                {openDeficiencies.length === 0 && (
                  <div className="px-3 py-2 text-sm text-muted-foreground">
                    미해결·처리중 미비점이 없습니다
                  </div>
                )}
                {openDeficiencies.map((d) => (
                  <SelectItem key={d.id} value={d.id}>
                    <span className="font-medium">{d.code}</span>
                    <span className="ml-1 text-muted-foreground">
                      — {d.description.length > 40 ? d.description.slice(0, 40) + '…' : d.description}
                    </span>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-1.5">
            <Label>
              담당자 <span className="text-destructive">*</span>
            </Label>
            <Select
              value={form.owner_id}
              onValueChange={(v) => setForm((f) => ({ ...f, owner_id: v }))}
            >
              <SelectTrigger>
                <SelectValue placeholder="담당자 선택..." />
              </SelectTrigger>
              <SelectContent>
                {activeUsers.length === 0 && (
                  <div className="px-3 py-2 text-sm text-muted-foreground">
                    활성 사용자가 없습니다
                  </div>
                )}
                {activeUsers.map((u) => (
                  <SelectItem key={u.id} value={u.id}>
                    {u.display_name}
                    <span className="ml-1 text-muted-foreground text-xs">({u.email})</span>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <Label htmlFor="target_date">
                목표일 <span className="text-destructive">*</span>
              </Label>
              <Input
                id="target_date"
                type="date"
                value={form.target_date}
                onChange={(e) => setForm((f) => ({ ...f, target_date: e.target.value }))}
              />
            </div>

            <div className="space-y-1.5">
              <Label>우선순위</Label>
              <Select
                value={form.priority}
                onValueChange={(v) => setForm((f) => ({ ...f, priority: v as RemediationPriority }))}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="High">상 (High)</SelectItem>
                  <SelectItem value="Medium">중 (Medium)</SelectItem>
                  <SelectItem value="Low">하 (Low)</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="action_plan">
              개선 조치 내용 <span className="text-destructive">*</span>
            </Label>
            <Textarea
              id="action_plan"
              rows={3}
              placeholder="개선 조치 내용을 입력하세요"
              value={form.action_plan}
              onChange={(e) => setForm((f) => ({ ...f, action_plan: e.target.value }))}
            />
          </div>

          <div className="rounded-md bg-muted/50 px-3 py-2 text-sm text-muted-foreground">
            ⓘ 개선계획은 <strong>계획(planned)</strong> 상태로 생성됩니다.
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => handleOpenChange(false)}>
            취소
          </Button>
          <Button onClick={handleSubmit} disabled={createMutation.isPending}>
            {createMutation.isPending ? '등록 중...' : '등록'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
