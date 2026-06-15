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
import type { Control } from '../types'

interface Props {
  open: boolean
  control: Control | null
  onOpenChange: (open: boolean) => void
  onConfirm: () => void
  isPending: boolean
}

export default function DeleteConfirmDialog({ open, control, onOpenChange, onConfirm, isPending }: Props) {
  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>통제 삭제 확인</AlertDialogTitle>
          <AlertDialogDescription asChild>
            <div className="space-y-2">
              <p>정말 이 통제를 삭제하시겠습니까?</p>
              {control && (
                <p className="font-medium text-foreground">
                  {control.code} — {control.name}
                </p>
              )}
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
