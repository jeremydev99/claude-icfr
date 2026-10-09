import EmptyState from '@/components/illustration/EmptyState'
import { useMemo, useState } from 'react'
import { toast } from 'sonner'
import { Loader2, Lock, Plus, Trash2 } from 'lucide-react'
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
import { Card, CardContent } from '@/components/ui/card'
import HelpButton from '@/features/help/HelpButton'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { useAuthStore } from '@/features/auth/store'
import { isIcfrManagerForUser } from '@/features/auth/permissions.pure'
import { useUsers } from '@/features/users/api/useUsers'
import { useMemberships } from '../api/useOrg'
import {
  errorDetail,
  useAssignments,
  useDeleteAssignment,
  useTargetControls,
  useTargetProcesses,
  type RoleAssignment,
} from '../api/PolicyAssignmentApi'
import { ASSIGNMENT_ROLES, ASSIGNMENT_SCOPES, roleLabel, scopeLabel } from '../PolicyDefs.pure'
import AssignmentAddDialog from '../components/AssignmentAddDialog'
import RoleMatrix from '../roleMatrix/RoleMatrix'
import OfficerRoles from '../components/OfficerRoles'

const ALL = '__all__'

export default function RoleAssignmentsPage() {
  const { user } = useAuthStore()
  const canManage = isIcfrManagerForUser(user)

  const { data, isLoading, isError } = useAssignments()
  const { data: processes = [] } = useTargetProcesses()
  const { data: controls = [] } = useTargetControls()
  const { data: userData } = useUsers({ limit: 200 })
  const { data: memberData } = useMemberships()

  const [roleFilter, setRoleFilter] = useState(ALL)
  const [scopeFilter, setScopeFilter] = useState(ALL)
  const [search, setSearch] = useState('')
  const [addOpen, setAddOpen] = useState(false)
  // 기본은 표 — 통제 93개를 모달로 하나씩 하면 끝이 없다(2026-10-06 마스터)
  const [view, setView] = useState<'matrix' | 'list'>('matrix')
  const [deleteTarget, setDeleteTarget] = useState<RoleAssignment | null>(null)
  const del = useDeleteAssignment()

  const users = useMemo(
    () => (userData?.items ?? []).map((u) => ({ id: u.id, display_name: u.display_name })),
    [userData],
  )

  const rows = useMemo(() => {
    const targetMap = new Map<string, { code: string; name: string }>()
    for (const p of processes) targetMap.set(`process:${p.id}`, p)
    for (const c of controls) targetMap.set(`control:${c.id}`, c)
    const deptByUser = new Map<string, string>()
    for (const m of memberData?.items ?? []) {
      if (m.department_name && (m.is_primary || !deptByUser.has(m.user_id))) {
        deptByUser.set(m.user_id, m.department_name)
      }
    }
    return (data?.items ?? []).map((a) => {
      const t = targetMap.get(`${a.scope}:${a.target_id}`)
      return {
        ...a,
        targetCode: t?.code ?? '(대상 없음)',
        targetName: t?.name ?? a.target_id,
        dept: deptByUser.get(a.user_id) ?? '',
      }
    })
  }, [data, processes, controls, memberData])

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase()
    return rows
      .filter((r) => roleFilter === ALL || r.role_name === roleFilter)
      .filter((r) => scopeFilter === ALL || r.scope === scopeFilter)
      .filter(
        (r) =>
          !q ||
          `${r.targetCode} ${r.targetName} ${r.user_name ?? ''} ${r.dept}`.toLowerCase().includes(q),
      )
      .sort((a, b) => a.targetCode.localeCompare(b.targetCode) || a.role_name.localeCompare(b.role_name))
  }, [rows, roleFilter, scopeFilter, search])

  const confirmDelete = async () => {
    if (!deleteTarget) return
    try {
      await del.mutateAsync(deleteTarget.id)
      toast.success('배정을 삭제했습니다')
      setDeleteTarget(null)
    } catch (e) {
      toast.error(errorDetail(e, '삭제하지 못했습니다'))
    }
  }

  return (
    <div className="mx-auto max-w-[1400px] space-y-6 p-6 md:p-8">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">역할 배정</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            역할은 사람이 아니라 통제에 붙습니다. 프로세스 배정은 소속 통제의 기본값이며, 통제별 배정이 우선합니다.
            이해상충(겸직) 조합은 사유를 남겨야 저장되고, 정책에서 금지하면 거부됩니다.
          </p>
        </div>
        {canManage ? (
          <Button onClick={() => setAddOpen(true)}>
            <Plus className="mr-1 h-4 w-4" /> 배정 추가
          </Button>
        ) : (
          <Badge variant="outline">
            <Lock className="mr-1 h-3 w-3" /> 읽기 전용 · 내부회계관리자만 편집
          </Badge>
        )}
      </div>

      <section className="space-y-2">
        <h2 className="text-base font-semibold">회사 직책 <HelpButton k="screen.admin.role-assignments.officers" /> <span className="text-sm font-normal text-muted-foreground">— 보고서 서명자·법정 보고 주체. 지정한 사람이 보고서 기본 정보에 자동으로 들어갑니다</span></h2>
        <OfficerRoles canEdit={canManage} />
      </section>

      <h2 className="text-base font-semibold">통제별 역할 <HelpButton k={view === 'matrix' ? 'screen.admin.role-assignments.matrix' : 'screen.admin.role-assignments.list'} /> <span className="text-sm font-normal text-muted-foreground">— 통제책임자·부서승인자·평가자</span></h2>
      <div className="flex w-fit items-center gap-1 rounded-md border p-1">
        <Button size="sm" variant={view === 'matrix' ? 'default' : 'ghost'} onClick={() => setView('matrix')}>일괄 배정 표</Button>
        <Button size="sm" variant={view === 'list' ? 'default' : 'ghost'} onClick={() => setView('list')}>배정 목록</Button>
      </div>

      {view === 'matrix' && <RoleMatrix />}

      {view === 'list' && (
      <Card>
        <CardContent className="space-y-3 pt-6">
          <div className="flex flex-wrap gap-2">
            <Select value={scopeFilter} onValueChange={setScopeFilter}>
              <SelectTrigger className="w-44">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={ALL}>범위 전체</SelectItem>
                {ASSIGNMENT_SCOPES.map((s) => (
                  <SelectItem key={s.value} value={s.value}>
                    {s.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select value={roleFilter} onValueChange={setRoleFilter}>
              <SelectTrigger className="w-40">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={ALL}>역할 전체</SelectItem>
                {ASSIGNMENT_ROLES.map((r) => (
                  <SelectItem key={r.value} value={r.value}>
                    {r.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Input
              className="w-64"
              placeholder="대상 코드·이름, 담당자, 부서 검색"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
            <span className="self-center text-sm text-muted-foreground">
              {filtered.length} / {rows.length}건
            </span>
          </div>

          {isLoading ? (
            <div className="flex items-center gap-2 py-8 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" /> 불러오는 중…
            </div>
          ) : isError ? (
            <p className="py-8 text-sm text-destructive">배정 목록을 불러오지 못했습니다.</p>
          ) : filtered.length === 0 ? (
            rows.length === 0 ? (
              <EmptyState compact slot="empty-people" title="아직 배정이 없습니다." />
            ) : (
              <EmptyState compact slot="empty-search" title="조건에 맞는 배정이 없습니다." />
            )
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>범위</TableHead>
                    <TableHead>대상</TableHead>
                    <TableHead>역할</TableHead>
                    <TableHead>담당자</TableHead>
                    <TableHead>부서</TableHead>
                    {canManage && <TableHead className="w-12" />}
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filtered.map((r) => (
                    <TableRow key={r.id}>
                      <TableCell>
                        <Badge variant={r.scope === 'control' ? 'default' : 'secondary'}>
                          {scopeLabel(r.scope)}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <div className="font-mono text-xs text-muted-foreground">{r.targetCode}</div>
                        <div>{r.targetName}</div>
                      </TableCell>
                      <TableCell>{roleLabel(r.role_name)}</TableCell>
                      <TableCell>{r.user_name ?? r.user_id}</TableCell>
                      <TableCell className="text-muted-foreground">{r.dept || '-'}</TableCell>
                      {canManage && (
                        <TableCell>
                          <Button
                            variant="ghost"
                            size="icon"
                            aria-label="배정 삭제"
                            onClick={() => setDeleteTarget(r)}
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </TableCell>
                      )}
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>
      )}

      {canManage && (
        <AssignmentAddDialog
          open={addOpen}
          onOpenChange={setAddOpen}
          processes={processes}
          controls={controls}
          users={users}
        />
      )}

      <AlertDialog open={!!deleteTarget} onOpenChange={(o) => !o && setDeleteTarget(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>배정을 삭제할까요?</AlertDialogTitle>
            <AlertDialogDescription>
              {deleteTarget &&
                `${scopeLabel(deleteTarget.scope)} · ${roleLabel(deleteTarget.role_name)} · ${
                  deleteTarget.user_name ?? ''
                }`}
              <br />
              통제 배정을 지우면 프로세스 기본값(또는 부서 책임자 유도)으로 돌아갑니다.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>취소</AlertDialogCancel>
            <AlertDialogAction onClick={confirmDelete} disabled={del.isPending}>
              삭제
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
