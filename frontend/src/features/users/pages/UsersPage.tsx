import { useState } from 'react'
import { toast } from 'sonner'
import { Loader2 } from 'lucide-react'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import { Button } from '@/components/ui/button'
import { useUsers } from '../api/useUsers'
import { useUserRoles, useDeleteUserRole } from '../api/useUserRoles'
import UserTable from '../components/UserTable'
import UserDetailSheet from '../components/UserDetailSheet'
import UserRoleTable from '../components/UserRoleTable'
import UserRoleFormDialog from '../components/UserRoleFormDialog'
import type { User, UserRole } from '../types'

type ActiveTab = 'users' | 'roles'

export default function UsersPage() {
  const [activeTab, setActiveTab] = useState<ActiveTab>('users')

  // ── 사용자 상태 ──────────────────────────────────────────
  const { data: userData, isLoading: userLoading, isError: userError, error: userErr } =
    useUsers({ skip: 0, limit: 200 })

  const [selectedUser, setSelectedUser] = useState<User | null>(null)
  const [userDetailOpen, setUserDetailOpen] = useState(false)

  const handleUserRowClick = (user: User) => {
    setSelectedUser(user)
    setUserDetailOpen(true)
  }

  // ── 역할 상태 ────────────────────────────────────────────
  const { data: roleData, isLoading: roleLoading, isError: roleError, error: roleErr } =
    useUserRoles({ skip: 0, limit: 200 })
  const deleteRole = useDeleteUserRole()

  const [roleFormOpen, setRoleFormOpen] = useState(false)
  const [editTarget, setEditTarget] = useState<UserRole | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<UserRole | null>(null)

  const handleEditClick = (item: UserRole) => {
    setEditTarget(item)
    setRoleFormOpen(true)
  }

  const handleDeleteConfirm = async () => {
    if (!deleteTarget) return
    try {
      await deleteRole.mutateAsync(deleteTarget.id)
      toast.success('역할이 삭제되었습니다')
    } catch {
      toast.error('삭제에 실패했습니다')
    } finally {
      setDeleteTarget(null)
    }
  }

  const users = userData?.items ?? []

  return (
    <div className="p-6 space-y-4">
      <div>
        <h1 className="text-2xl font-semibold">담당자/권한 (User & Role)</h1>
        <p className="text-sm text-muted-foreground mt-1">
          사용자 조회 및 역할 관리
        </p>
      </div>

      {/* 탭 토글 */}
      <div className="flex items-center gap-1 border rounded-md p-1 w-fit">
        <Button
          variant={activeTab === 'users' ? 'default' : 'ghost'}
          size="sm"
          onClick={() => setActiveTab('users')}
        >
          사용자
        </Button>
        <Button
          variant={activeTab === 'roles' ? 'default' : 'ghost'}
          size="sm"
          onClick={() => setActiveTab('roles')}
        >
          역할 관리
        </Button>
      </div>

      {/* 사용자 뷰 */}
      {activeTab === 'users' && (
        <UserTable
          data={userData}
          isLoading={userLoading}
          isError={userError}
          error={userErr}
          onRowClick={handleUserRowClick}
        />
      )}

      {/* 역할 관리 뷰 */}
      {activeTab === 'roles' && (
        <div className="space-y-3">
          <div className="flex justify-end">
            <Button
              size="sm"
              onClick={() => { setEditTarget(null); setRoleFormOpen(true) }}
            >
              + 역할 등록
            </Button>
          </div>
          <UserRoleTable
            data={roleData}
            users={users}
            isLoading={roleLoading}
            isError={roleError}
            error={roleErr}
            onAddClick={() => { setEditTarget(null); setRoleFormOpen(true) }}
            onEditClick={handleEditClick}
            onDeleteClick={(item) => setDeleteTarget(item)}
          />
        </div>
      )}

      {/* Sheets / Dialogs */}
      <UserDetailSheet
        userId={selectedUser?.id ?? null}
        open={userDetailOpen}
        onOpenChange={setUserDetailOpen}
      />

      <UserRoleFormDialog
        open={roleFormOpen}
        onOpenChange={(o) => { setRoleFormOpen(o); if (!o) setEditTarget(null) }}
        editTarget={editTarget}
      />

      <AlertDialog
        open={!!deleteTarget}
        onOpenChange={(o) => { if (!o) setDeleteTarget(null) }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              역할을 삭제하시겠습니까?
            </AlertDialogTitle>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>취소</AlertDialogCancel>
            <AlertDialogAction
              className="bg-red-600 hover:bg-red-700"
              onClick={handleDeleteConfirm}
              disabled={deleteRole.isPending}
            >
              {deleteRole.isPending && <Loader2 className="h-3.5 w-3.5 mr-1 animate-spin" />}
              삭제
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
