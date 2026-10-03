import EmptyState from '@/components/illustration/EmptyState'
import { Loader2, KeyRound, LockOpen, Pencil, Trash2 } from 'lucide-react'
import { formatDate } from '@/lib/utils'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import type { User, UserListResponse } from '../types'
import { isLocked } from '../loginEvents.pure'

interface Props {
  data: UserListResponse | undefined
  isLoading: boolean
  isError: boolean
  error: Error | null | unknown
  onRowClick: (user: User) => void
  onEditClick: (user: User) => void
  onDeleteClick: (user: User) => void
  onResetPasswordClick: (user: User) => void
  /** 잠긴 계정 해제 (보안 1단계) */
  onUnlockClick?: (user: User) => void
}

export default function UserTable({
  data,
  isLoading,
  isError,
  error,
  onRowClick,
  onEditClick,
  onDeleteClick,
  onResetPasswordClick,
  onUnlockClick,
}: Props) {
  const { items = [], total = 0 } = data ?? {}

  if (isLoading) {
    return (
      <div className="flex items-center justify-center p-12 text-muted-foreground gap-2">
        <Loader2 className="h-5 w-5 animate-spin" />
        불러오는 중...
      </div>
    )
  }

  if (isError) {
    return (
      <div className="rounded-md border p-8 text-center text-sm text-destructive">
        데이터를 불러오지 못했습니다.{' '}
        {error instanceof Error ? error.message : '잠시 후 다시 시도해주세요.'}
      </div>
    )
  }

  if (items.length === 0) {
    return (
      <EmptyState slot="empty-people" title="등록된 사용자가 없습니다" description="사용자 등록 버튼으로 첫 사용자를 추가하세요." />
    )
  }

  return (
    <div className="space-y-2">
      <div className="text-sm text-muted-foreground">총 {total}명</div>
      <div className="overflow-hidden rounded-xl border bg-card shadow-card">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>이름</TableHead>
              <TableHead>이메일</TableHead>
              <TableHead>역할</TableHead>
              <TableHead>상태</TableHead>
              <TableHead>등록일</TableHead>
              <TableHead className="w-28"></TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {items.map((user) => (
              <TableRow
                key={user.id}
                className="cursor-pointer hover:bg-muted/50"
                onClick={() => onRowClick(user)}
              >
                <TableCell className="font-medium">{user.display_name}</TableCell>
                <TableCell className="text-sm text-muted-foreground">{user.email}</TableCell>
                <TableCell>
                  <Badge variant="outline">{user.role}</Badge>
                </TableCell>
                <TableCell>
                  <Badge
                    variant="outline"
                    className={
                      user.is_active
                        ? 'bg-green-50 text-green-700 border-green-200'
                        : 'bg-gray-50 text-gray-500 border-gray-200'
                    }
                  >
                    {user.is_active ? '활성' : '비활성'}
                  </Badge>
                  {isLocked(user.locked_until) && (
                    <Badge variant="outline" className="ml-1 bg-red-50 text-red-700 border-red-200" title={`해제 예정 ${new Date(user.locked_until!).toLocaleString('ko-KR')}`}>
                      잠김
                    </Badge>
                  )}
                </TableCell>
                <TableCell className="text-sm text-muted-foreground">
                  {formatDate(user.created_at)}
                </TableCell>
                <TableCell onClick={(e) => e.stopPropagation()}>
                  <div className="flex items-center gap-1">
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-7 w-7"
                      title="편집"
                      onClick={() => onEditClick(user)}
                    >
                      <Pencil className="h-3.5 w-3.5" />
                    </Button>
                    {isLocked(user.locked_until) && onUnlockClick && (
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-7 w-7 text-red-600"
                        title="잠금 해제"
                        onClick={() => onUnlockClick(user)}
                      >
                        <LockOpen className="h-3.5 w-3.5" />
                      </Button>
                    )}
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-7 w-7"
                      title="비밀번호 재설정"
                      onClick={() => onResetPasswordClick(user)}
                    >
                      <KeyRound className="h-3.5 w-3.5" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-7 w-7 hover:bg-red-50 hover:text-red-600"
                      title="삭제"
                      onClick={() => onDeleteClick(user)}
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </Button>
                  </div>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  )
}
