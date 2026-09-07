// DeleteConfirmDialog.tsx(Control 전용)의 패턴을 3계층(Process/SubProcess/Risk) 공용으로 일반화.
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import type { SourceEnvelope } from '../../api/sourceEnvelope'
import { resolveDeleteSemantics } from '../../api/sourceEnvelope'

interface Target {
  label: string
  envelope: SourceEnvelope
}

interface Props {
  open: boolean
  target: Target | null
  itemTypeLabel: string
  onOpenChange: (open: boolean) => void
  onConfirm: () => void
  isPending: boolean
}

export default function HierarchyDeleteConfirmDialog({
  open,
  target,
  itemTypeLabel,
  onOpenChange,
  onConfirm,
  isPending,
}: Props) {
  const semantics = resolveDeleteSemantics(target?.envelope)
  const isExclude = semantics === 'exclude'

  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>{isExclude ? `기준 ${itemTypeLabel} 제외 확인` : `${itemTypeLabel} 삭제 확인`}</AlertDialogTitle>
          <AlertDialogDescription asChild>
            <div className="space-y-2">
              <p>
                {isExclude
                  ? `이 ${itemTypeLabel}은(는) 기준(baseline)입니다. 삭제 시 귀사 범위에서 제외 처리되며 기준 자체는 보존됩니다.`
                  : `이 ${itemTypeLabel}을(를) 삭제합니다.`}
              </p>
              {target && <p className="font-medium text-foreground">{target.label}</p>}
              <p className="text-destructive">이 작업은 되돌릴 수 없습니다.</p>
            </div>
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel disabled={isPending}>취소</AlertDialogCancel>
          <AlertDialogAction
            onClick={(e) => {
              e.preventDefault()
              onConfirm()
            }}
            disabled={isPending}
            className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
          >
            {isPending ? '삭제 중...' : '삭제'}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}
