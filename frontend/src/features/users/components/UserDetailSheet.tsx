import { Loader2 } from 'lucide-react'
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet'
import { Badge } from '@/components/ui/badge'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { useUserDetail } from '../api/useUsers'
import { useUserRoles } from '../api/useUserRoles'
import { ROLE_NAME_OPTIONS } from '../types'

interface Props {
  userId: string | null
  open: boolean
  onOpenChange: (open: boolean) => void
}

function InfoRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex gap-3 py-2 border-b last:border-0">
      <span className="w-24 shrink-0 text-sm text-muted-foreground">{label}</span>
      <span className="text-sm">{children}</span>
    </div>
  )
}

export default function UserDetailSheet({ userId, open, onOpenChange }: Props) {
  const { data: user, isLoading } = useUserDetail(userId)
  const { data: rolesData } = useUserRoles({ skip: 0, limit: 200 })

  const userRoles = rolesData?.items.filter((r) => r.user_id === userId) ?? []

  const roleLabel = (roleName: string) =>
    ROLE_NAME_OPTIONS.find((o) => o.value === roleName)?.label ?? roleName

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="w-[420px] sm:max-w-[420px] overflow-y-auto">
        <SheetHeader className="mb-4">
          <SheetTitle>사용자 상세</SheetTitle>
        </SheetHeader>

        {isLoading && (
          <div className="flex justify-center py-12">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
          </div>
        )}

        {user && (
          <div className="space-y-6">
            {/* 기본 정보 */}
            <div>
              <h3 className="text-sm font-semibold mb-2">기본 정보</h3>
              <div className="rounded-md border px-3">
                <InfoRow label="이름">{user.display_name}</InfoRow>
                <InfoRow label="이메일">{user.email}</InfoRow>
                <InfoRow label="기본 역할">
                  <Badge variant="outline">{user.role}</Badge>
                </InfoRow>
                <InfoRow label="상태">
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
                </InfoRow>
                <InfoRow label="등록일">
                  {new Date(user.created_at).toLocaleDateString('ko-KR')}
                </InfoRow>
              </div>
            </div>

            {/* 할당된 역할 */}
            <div>
              <h3 className="text-sm font-semibold mb-2">
                할당된 역할{' '}
                <span className="font-normal text-muted-foreground">({userRoles.length}건)</span>
              </h3>
              {userRoles.length === 0 ? (
                <div className="rounded-md border p-6 text-center text-sm text-muted-foreground">
                  할당된 역할이 없습니다.
                </div>
              ) : (
                <div className="rounded-md border">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>역할</TableHead>
                        <TableHead>범위</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {userRoles.map((r) => (
                        <TableRow key={r.id}>
                          <TableCell>
                            <Badge variant="secondary">{roleLabel(r.role_name)}</Badge>
                          </TableCell>
                          <TableCell className="text-sm text-muted-foreground">
                            {r.scope ?? '—'}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              )}
            </div>
          </div>
        )}
      </SheetContent>
    </Sheet>
  )
}
