import { useMemo, useState } from 'react'
import { toast } from 'sonner'
import { Link } from 'react-router-dom'
import { Loader2, Lock, Plus, Star, Trash2, UserPlus } from 'lucide-react'
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
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { cn } from '@/lib/utils'
import { useAuthStore } from '@/features/auth/store'
import { isIcfrManagerForUser } from '@/features/auth/permissions.pure'
import { useUsers } from '@/features/users/api/useUsers'
import {
  useCreateDepartment,
  useCreateMembership,
  useDeleteDepartment,
  useDeleteMembership,
  useDepartments,
  useMemberships,
  useUpdateDepartment,
  useUpdateMembership,
} from '../api/useOrg'
import DepartmentFormDialog from '../components/DepartmentFormDialog'
import MemberAddDialog from '../components/MemberAddDialog'
import type { Department, DepartmentPayload } from '../types'

/** 서버가 보낸 문구를 그대로 쓴다 — "소속 인원 1명이 남아…" 처럼 사용자가 할 일을 알려준다. */
const errorDetail = (e: unknown, fallback: string) =>
  (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? fallback

export default function DepartmentsPage() {
  const { user } = useAuthStore()
  // **`can_write` 가 아니라 `tenant_roles` 로 본다** — can_write 는 external_auditor 판정이지
  // icfr_manager 판정이 아니다. 서버도 부서·소속 쓰기에 require_icfr_manager 를 건다.
  const canManage = isIcfrManagerForUser(user)

  const { data: deptData, isLoading, isError } = useDepartments()
  const { data: userData } = useUsers({ limit: 200 })
  const { data: allMemberData } = useMemberships()

  const departments = useMemo(() => deptData?.items ?? [], [deptData])
  const users = useMemo(
    () => (userData?.items ?? []).map((u) => ({ id: u.id, display_name: u.display_name })),
    [userData],
  )
  const allMemberships = useMemo(() => allMemberData?.items ?? [], [allMemberData])

  const [selectedId, setSelectedId] = useState<string | null>(null)
  const selected = departments.find((d) => d.id === selectedId) ?? departments[0] ?? null
  const members = allMemberships.filter((m) => m.department_id === selected?.id)

  const [formOpen, setFormOpen] = useState(false)
  const [editing, setEditing] = useState<Department | null>(null)
  const [memberOpen, setMemberOpen] = useState(false)
  const [deleteTarget, setDeleteTarget] = useState<Department | null>(null)

  const createDept = useCreateDepartment()
  const updateDept = useUpdateDepartment()
  const deleteDept = useDeleteDepartment()
  const createMember = useCreateMembership()
  const updateMember = useUpdateMembership()
  const deleteMember = useDeleteMembership()

  const submitDept = async (body: DepartmentPayload) => {
    try {
      if (editing) await updateDept.mutateAsync({ id: editing.id, body })
      else await createDept.mutateAsync(body)
      toast.success(editing ? '부서를 수정했습니다' : '부서를 등록했습니다')
      setFormOpen(false)
    } catch (e) {
      toast.error(errorDetail(e, '저장하지 못했습니다'))
    }
  }

  const confirmDelete = async () => {
    if (!deleteTarget) return
    try {
      await deleteDept.mutateAsync(deleteTarget.id)
      toast.success('부서를 삭제했습니다')
      if (selectedId === deleteTarget.id) setSelectedId(null)
      setDeleteTarget(null)
    } catch (e) {
      // 소속이 남아 있으면 409 — 서버 문구가 무엇을 먼저 해야 하는지 알려준다
      toast.error(errorDetail(e, '삭제하지 못했습니다'))
    }
  }

  const addMember = async (userId: string, isPrimary: boolean) => {
    if (!selected) return
    try {
      await createMember.mutateAsync({
        user_id: userId, department_id: selected.id, is_primary: isPrimary,
      })
      toast.success('인원을 추가했습니다')
      setMemberOpen(false)
    } catch (e) {
      toast.error(errorDetail(e, '추가하지 못했습니다'))
    }
  }

  const togglePrimary = async (membershipId: string, next: boolean) => {
    try {
      await updateMember.mutateAsync({ id: membershipId, isPrimary: next })
      toast.success(next ? '주 소속으로 지정했습니다' : '주 소속을 해제했습니다')
    } catch (e) {
      toast.error(errorDetail(e, '변경하지 못했습니다'))
    }
  }

  const removeMember = async (membershipId: string) => {
    try {
      await deleteMember.mutateAsync(membershipId)
      toast.success('소속을 해제했습니다')
    } catch (e) {
      toast.error(errorDetail(e, '해제하지 못했습니다'))
    }
  }

  if (isLoading) {
    return (
      <div className="flex items-center gap-2 p-6 text-sm text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" /> 불러오는 중…
      </div>
    )
  }
  if (isError) {
    return <div className="p-6 text-sm text-destructive">부서를 불러오지 못했습니다</div>
  }

  return (
    <div className="space-y-4 p-6">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h1 className="text-2xl font-semibold">부서 관리</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            부서와 소속 인원을 관리합니다. 통제책임자의 <strong>주 소속</strong>이{' '}
            <Link to="/dashboard" className="underline">대시보드</Link>의 통제 조직별 집계 기준입니다.
          </p>
        </div>
        {canManage ? (
          <Button onClick={() => { setEditing(null); setFormOpen(true) }}>
            <Plus className="mr-1 h-4 w-4" /> 부서 등록
          </Button>
        ) : (
          // 감추지 않고 읽기 전용으로 둔다 — 조직도를 보는 것 자체는 막을 이유가 없고,
          // 메뉴가 사라지면 "그런 기능이 있는지"조차 모른다.
          <Badge variant="secondary" className="gap-1">
            <Lock className="h-3 w-3" /> 읽기 전용 · 내부회계관리자만 편집
          </Badge>
        )}
      </div>

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)]">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">부서 {departments.length}개</CardTitle>
          </CardHeader>
          <CardContent>
            {departments.length === 0 && (
              <p className="text-sm text-muted-foreground">
                등록된 부서가 없습니다. 부서를 만들면 대시보드의 &ldquo;미배정&rdquo;이 풀리기 시작합니다.
              </p>
            )}
            <ul className="divide-y">
              {departments.map((d) => {
                const count = allMemberships.filter((m) => m.department_id === d.id).length
                return (
                  <li key={d.id}>
                    <div
                      className={cn(
                        'flex items-center gap-2 py-2',
                        selected?.id === d.id && 'font-medium',
                      )}
                    >
                      <button
                        type="button"
                        onClick={() => setSelectedId(d.id)}
                        className="flex-1 text-left text-sm hover:underline"
                      >
                        {d.name}
                        <span className="ml-2 text-xs text-muted-foreground">
                          {count}명{d.manager_name ? ` · 책임자 ${d.manager_name}` : ''}
                        </span>
                      </button>
                      {canManage && (
                        <>
                          <Button
                            variant="ghost" size="sm"
                            onClick={() => { setEditing(d); setFormOpen(true) }}
                          >
                            수정
                          </Button>
                          <Button variant="ghost" size="sm" onClick={() => setDeleteTarget(d)}>
                            <Trash2 className="h-3.5 w-3.5" />
                          </Button>
                        </>
                      )}
                    </div>
                  </li>
                )
              })}
            </ul>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center justify-between gap-2 text-base">
              <span>{selected ? `${selected.name} 소속 인원` : '소속 인원'}</span>
              {canManage && selected && (
                <Button size="sm" variant="outline" onClick={() => setMemberOpen(true)}>
                  <UserPlus className="mr-1 h-3.5 w-3.5" /> 인원 추가
                </Button>
              )}
            </CardTitle>
          </CardHeader>
          <CardContent>
            {!selected && <p className="text-sm text-muted-foreground">부서를 선택하세요</p>}
            {selected && members.length === 0 && (
              <p className="text-sm text-muted-foreground">소속 인원이 없습니다</p>
            )}
            <ul className="divide-y">
              {members.map((m) => (
                <li key={m.id} className="flex items-center gap-2 py-2 text-sm">
                  <span className="flex-1">{m.user_name}</span>
                  {m.is_primary ? (
                    <Badge variant="default" className="gap-1">
                      <Star className="h-3 w-3" /> 주 소속
                    </Badge>
                  ) : (
                    canManage && (
                      <Button variant="ghost" size="sm" onClick={() => togglePrimary(m.id, true)}>
                        주 소속으로
                      </Button>
                    )
                  )}
                  {canManage && (
                    <Button variant="ghost" size="sm" onClick={() => removeMember(m.id)}>
                      <Trash2 className="h-3.5 w-3.5" />
                    </Button>
                  )}
                </li>
              ))}
            </ul>
            {selected && (
              <p className="pt-3 text-xs text-muted-foreground">
                주 소속은 사람마다 한 곳입니다. 다른 부서에서 주 소속이던 사람을 여기서 주 소속으로
                지정하면 <strong>옮겨집니다</strong>(기존 부서의 소속은 유지되고 표시만 해제).
              </p>
            )}
          </CardContent>
        </Card>
      </div>

      <DepartmentFormDialog
        open={formOpen}
        onOpenChange={setFormOpen}
        target={editing}
        users={users}
        onSubmit={submitDept}
        pending={createDept.isPending || updateDept.isPending}
      />

      {selected && (
        <MemberAddDialog
          open={memberOpen}
          onOpenChange={setMemberOpen}
          department={selected}
          users={users}
          allMemberships={allMemberships}
          onSubmit={addMember}
          pending={createMember.isPending}
        />
      )}

      <AlertDialog open={deleteTarget !== null} onOpenChange={(o) => !o && setDeleteTarget(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>부서를 삭제할까요?</AlertDialogTitle>
            <AlertDialogDescription>
              「{deleteTarget?.name}」을 삭제합니다. 소속 인원이 남아 있으면 삭제되지 않습니다 —
              먼저 소속을 정리해야 합니다.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>취소</AlertDialogCancel>
            <AlertDialogAction onClick={confirmDelete}>삭제</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
