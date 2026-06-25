import { Loader2, Pencil, Trash2 } from 'lucide-react'
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
import type { UserRole, UserRoleListResponse, User } from '../types'
import { ROLE_NAME_OPTIONS } from '../types'

interface Props {
  data: UserRoleListResponse | undefined
  users: User[]
  isLoading: boolean
  isError: boolean
  error: Error | null | unknown
  onAddClick: () => void
  onEditClick: (item: UserRole) => void
  onDeleteClick: (item: UserRole) => void
}

export default function UserRoleTable({
  data,
  users,
  isLoading,
  isError,
  error,
  onAddClick,
  onEditClick,
  onDeleteClick,
}: Props) {
  const { items = [], total = 0 } = data ?? {}

  const userMap = Object.fromEntries(users.map((u) => [u.id, u]))
  const roleLabel = (roleName: string) =>
    ROLE_NAME_OPTIONS.find((o) => o.value === roleName)?.label ?? roleName

  if (isLoading) {
    return (
      <div className="flex justify-center items-center py-20">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
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
      <div className="rounded-md border p-12 text-center text-sm text-muted-foreground">
        등록된 역할이 없습니다.{' '}
        <button
          className="underline underline-offset-2 hover:text-foreground"
          onClick={onAddClick}
        >
          역할 등록
        </button>{' '}
        버튼으로 첫 역할을 추가하세요.
      </div>
    )
  }

  return (
    <div className="space-y-2">
      <div className="text-sm text-muted-foreground">총 {total}건</div>
      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>사용자</TableHead>
              <TableHead>역할</TableHead>
              <TableHead>범위</TableHead>
              <TableHead>등록일</TableHead>
              <TableHead className="w-20"></TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {items.map((item) => {
              const u = userMap[item.user_id]
              return (
                <TableRow key={item.id}>
                  <TableCell>
                    <div className="text-sm font-medium">{u?.display_name ?? item.user_id}</div>
                    {u && (
                      <div className="text-xs text-muted-foreground">{u.email}</div>
                    )}
                  </TableCell>
                  <TableCell>
                    <Badge variant="secondary">{roleLabel(item.role_name)}</Badge>
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground">
                    {item.scope ?? '—'}
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground">
                    {new Date(item.created_at).toLocaleDateString('ko-KR')}
                  </TableCell>
                  <TableCell onClick={(e) => e.stopPropagation()}>
                    <div className="flex items-center gap-1">
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-7 w-7"
                        onClick={() => onEditClick(item)}
                      >
                        <Pencil className="h-3.5 w-3.5" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-7 w-7 hover:bg-red-50 hover:text-red-600"
                        onClick={() => onDeleteClick(item)}
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              )
            })}
          </TableBody>
        </Table>
      </div>
    </div>
  )
}
