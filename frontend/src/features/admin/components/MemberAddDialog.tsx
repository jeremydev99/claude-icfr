import { useEffect, useMemo, useState } from 'react'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import type { Department, Membership } from '../types'

interface Props {
  open: boolean
  onOpenChange: (open: boolean) => void
  department: Department
  users: Array<{ id: string; display_name: string }>
  /** 테넌트 전체 소속 — 이미 이 부서에 있는 사람 제외 + 기존 주 소속 안내에 쓴다 */
  allMemberships: Membership[]
  onSubmit: (userId: string, isPrimary: boolean) => Promise<void>
  pending: boolean
}

export default function MemberAddDialog({
  open, onOpenChange, department, users, allMemberships, onSubmit, pending,
}: Props) {
  const [userId, setUserId] = useState<string>('')
  const [isPrimary, setIsPrimary] = useState(false)

  useEffect(() => {
    if (!open) return
    setUserId('')
    setIsPrimary(false)
  }, [open])

  // 이미 이 부서에 있는 사람은 고를 수 없다 — 고르면 409 가 돌아온다.
  const alreadyIn = useMemo(
    () => new Set(allMemberships.filter((m) => m.department_id === department.id).map((m) => m.user_id)),
    [allMemberships, department.id],
  )
  const candidates = users.filter((u) => !alreadyIn.has(u.id))

  // **주 소속은 하나다.** 서버는 거부하지 않고 옮긴다 — 옮겨질 곳을 미리 알려준다.
  const currentPrimary = allMemberships.find((m) => m.user_id === userId && m.is_primary)

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{department.name} — 인원 추가</DialogTitle>
          <DialogDescription>
            한 사람이 여러 부서에 속할 수 있습니다. 주 소속은 한 곳뿐입니다.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-2">
          <div className="space-y-1.5">
            <Label htmlFor="member-user">사용자</Label>
            <Select value={userId} onValueChange={setUserId}>
              <SelectTrigger id="member-user">
                <SelectValue placeholder="선택" />
              </SelectTrigger>
              <SelectContent>
                {candidates.map((u) => (
                  <SelectItem key={u.id} value={u.id}>
                    {u.display_name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {candidates.length === 0 && (
              <p className="text-xs text-muted-foreground">추가할 수 있는 사용자가 없습니다</p>
            )}
          </div>

          <div className="flex items-start gap-2">
            <Checkbox
              id="member-primary"
              checked={isPrimary}
              onCheckedChange={(v) => setIsPrimary(v === true)}
            />
            <div className="space-y-1">
              <Label htmlFor="member-primary" className="cursor-pointer">
                주 소속으로 지정
              </Label>
              <p className="text-xs text-muted-foreground">
                부서승인 단계의 승인자를 정하는 기준입니다.
              </p>
              {isPrimary && currentPrimary && (
                <p className="text-xs font-medium text-amber-700">
                  기존 주 소속 「{currentPrimary.department_name}」에서 옮겨집니다.
                </p>
              )}
            </div>
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={pending}>
            취소
          </Button>
          <Button onClick={() => onSubmit(userId, isPrimary)} disabled={pending || !userId}>
            추가
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
