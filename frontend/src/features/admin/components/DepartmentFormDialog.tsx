import { useEffect, useState } from 'react'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import type { Department, DepartmentPayload } from '../types'

const NO_MANAGER = '__none__'

interface Props {
  open: boolean
  onOpenChange: (open: boolean) => void
  /** null 이면 생성, 값이 있으면 수정 */
  target: Department | null
  users: Array<{ id: string; display_name: string }>
  onSubmit: (body: DepartmentPayload) => Promise<void>
  pending: boolean
}

export default function DepartmentFormDialog({
  open, onOpenChange, target, users, onSubmit, pending,
}: Props) {
  const [name, setName] = useState('')
  const [managerId, setManagerId] = useState<string>(NO_MANAGER)

  useEffect(() => {
    if (!open) return
    setName(target?.name ?? '')
    setManagerId(target?.manager_id ?? NO_MANAGER)
  }, [open, target])

  const handleSubmit = async () => {
    await onSubmit({
      name: name.trim(),
      manager_id: managerId === NO_MANAGER ? null : managerId,
    })
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{target ? '부서 수정' : '부서 등록'}</DialogTitle>
          <DialogDescription>
            부서 책임자는 그 부서 소속이 아니어도 되고, 한 사람이 여러 부서를 겸임할 수 있습니다.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-2">
          <div className="space-y-1.5">
            <Label htmlFor="dept-name">부서명</Label>
            <Input
              id="dept-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="예: 자금팀"
              maxLength={100}
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="dept-manager">부서 책임자</Label>
            <Select value={managerId} onValueChange={setManagerId}>
              <SelectTrigger id="dept-manager">
                <SelectValue placeholder="선택 안 함" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={NO_MANAGER}>선택 안 함</SelectItem>
                {users.map((u) => (
                  <SelectItem key={u.id} value={u.id}>
                    {u.display_name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <p className="text-xs text-muted-foreground">
              부서승인 단계의 승인자가 됩니다(통제책임자의 주 소속 부서 기준).
            </p>
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={pending}>
            취소
          </Button>
          <Button onClick={handleSubmit} disabled={pending || name.trim().length === 0}>
            {target ? '수정' : '등록'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
