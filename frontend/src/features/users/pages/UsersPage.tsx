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
import { useUsers, useDeleteUser } from '../api/useUsers'
import { useUserRoles, useDeleteUserRole } from '../api/useUserRoles'
import UserTable from '../components/UserTable'
import UserDetailSheet from '../components/UserDetailSheet'
import UserFormDialog from '../components/UserFormDialog'
import ResetPasswordDialog from '../components/ResetPasswordDialog'
import UserRoleTable from '../components/UserRoleTable'
import UserRoleFormDialog from '../components/UserRoleFormDialog'
import type { User, UserRole } from '../types'

type ActiveTab = 'users' | 'roles'

const getErrorDetail = (e: unknown) =>
  (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail

export default function UsersPage() {
  const [activeTab, setActiveTab] = useState<ActiveTab>('users')

  // ── 사용자 상태 ──────────────────────────────────────────
  const { data: userData, isLoading: userLoading, isError: userError, error: userErr } =
    useUsers({ skip: 0, limit: 200 })

  const deleteUser = useDeleteUser()

  const [selectedUser, setSelectedUser] = useState<User | null>(null)
  const [userDetailOpen, setUserDetailOpen] = useState(false)

  const [userFormOpen, setUserFormOpen] = useState(false)
  const [editUserTarget, setEditUserTarget] = useState<User | null>(null)

  const [deleteUserTarget, setDeleteUserTarget] = useState<User | null>(null)

  const [resetPwdTarget, setResetPwdTarget] = useState<User | null>(null)
  const [resetPwdOpen, setResetPwdOpen] = useState(false)

  const handleUserRowClick = (user: User) => {
    setSelectedUser(user)
    setUserDetailOpen(true)
  }

  const handleUserEditClick = (user: User) => {
    setEditUserTarget(user)
    setUserFormOpen(true)
  }

  const handleUserDeleteConfirm = async () => {
    if (!deleteUserTarget) return
    try {
      await deleteUser.mutateAsync(deleteUserTarget.id)
      toast.success('사용자가 삭제되었습니다')
    } catch (e) {
      toast.error(getErrorDetail(e) ?? '삭제에 실패했습니다')
    } finally {
      setDeleteUserTarget(null)
    }
  }

  // ── 역할 상태 ────────────────────────────────────────────
  const { data: roleData, isLoading: roleLoading, isError: roleError, error: roleErr } =
    useUserRoles({ skip: 0, limit: 200 })
  const deleteRole = useDeleteUserRole()

  const [roleFormOpen, setRoleFormOpen] = useState(false)
  const [editRoleTarget, setEditRoleTarget] = useState<UserRole | null>(null)
  const [deleteRoleTarget, setDeleteRoleTarget] = useState<UserRole | null>(null)

  const handleRoleEditClick = (item: UserRole) => {
    setEditRoleTarget(item)
    setRoleFormOpen(true)
  }

  const handleRoleDeleteConfirm = async () => {
    if (!deleteRoleTarget) return
    try {
      await deleteRole.mutateAsync(deleteRoleTarget.id)
      toast.success('역할이 삭제되었습니다')
    } catch (e) {
      toast.error(getErrorDetail(e) ?? '삭제에 실패했습니다')
    } finally {
      setDeleteRoleTarget(null)
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
        <div className="space-y-3">
          <div className="flex justify-end">
            <Button
              size="sm"
              onClick={() => { setEditUserTarget(null); setUserFormOpen(true) }}
            >
              + 사용자 등록
            </Button>
          </div>
          <UserTable
            data={userData}
            isLoading={userLoading}
            isError={userError}
            error={userErr}
            onRowClick={handleUserRowClick}
            onEditClick={handleUserEditClick}
            onDeleteClick={(u) => setDeleteUserTarget(u)}
            onResetPasswordClick={(u) => { setResetPwdTarget(u); setResetPwdOpen(true) }}
          />
        </div>
      )}

      {/* 역할 관리 뷰 */}
      {activeTab === 'roles' && (
        <div className="space-y-3">
          <div className="flex justify-end">
            <Button
              size="sm"
              onClick={() => { setEditRoleTarget(null); setRoleFormOpen(true) }}
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
            onAddClick={() => { setEditRoleTarget(null); setRoleFormOpen(true) }}
            onEditClick={handleRoleEditClick}
            onDeleteClick={(item) => setDeleteRoleTarget(item)}
          />
        </div>
      )}

      {/* Sheets / Dialogs */}
      <UserDetailSheet
        userId={selectedUser?.id ?? null}
        open={userDetailOpen}
        onOpenChange={setUserDetailOpen}
      />

      <UserFormDialog
        open={userFormOpen}
        onOpenChange={(o) => { setUserFormOpen(o); if (!o) setEditUserTarget(null) }}
        editTarget={editUserTarget}
        onSuccess={() => toast.success(editUserTarget ? '사용자가 수정되었습니다' : '사용자가 등록되었습니다')}
      />

      <ResetPasswordDialog
        open={resetPwdOpen}
        onOpenChange={setResetPwdOpen}
        targetUser={resetPwdTarget}
        onSuccess={() => toast.success('비밀번호가 재설정되었습니다')}
      />

      {/* 사용자 삭제 확인 */}
      <AlertDialog
        open={!!deleteUserTarget}
        onOpenChange={(o) => { if (!o) setDeleteUserTarget(null) }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              사용자 [{deleteUserTarget?.display_name}]를 삭제하시겠습니까?
            </AlertDialogTitle>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>취소</AlertDialogCancel>
            <AlertDialogAction
              className="bg-red-600 hover:bg-red-700"
              onClick={handleUserDeleteConfirm}
              disabled={deleteUser.isPending}
            >
              {deleteUser.isPending && <Loader2 className="h-3.5 w-3.5 mr-1 animate-spin" />}
              삭제
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <UserRoleFormDialog
        open={roleFormOpen}
        onOpenChange={(o) => { setRoleFormOpen(o); if (!o) setEditRoleTarget(null) }}
        editTarget={editRoleTarget}
      />

      {/* 역할 삭제 확인 */}
      <AlertDialog
        open={!!deleteRoleTarget}
        onOpenChange={(o) => { if (!o) setDeleteRoleTarget(null) }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>역할을 삭제하시겠습니까?</AlertDialogTitle>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>취소</AlertDialogCancel>
            <AlertDialogAction
              className="bg-red-600 hover:bg-red-700"
              onClick={handleRoleDeleteConfirm}
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
