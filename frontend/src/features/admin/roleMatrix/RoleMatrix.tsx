import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { AlertTriangle, Loader2, Save, Search, Star, Undo2, Users } from 'lucide-react'
import apiClient from '@/lib/axios'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { useActiveTenantId, useAuthStore } from '@/features/auth/store'
import { isIcfrStaffForUser } from '@/features/auth/permissions.pure'
import {
  ROLES, ROLE_LABEL, effective, groupByProcess, matches, pkey, toChanges,
  type Filter, type MatrixControl, type Pending, type RoleMatrixData, type RoleName,
} from './roleMatrix.pure'

const FILTERS: { v: Filter; label: string }[] = [
  { v: 'all', label: '전체' }, { v: 'unassigned', label: '미배정 있음' }, { v: 'key', label: '핵심통제' },
  { v: 'iuc', label: 'IUC(정보) 사용' }, { v: 'euc', label: '그중 EUC(스프레드시트)' }, { v: 'conflict', label: '겸직' },
]
const INHERIT = '__inherit__'
const NONE = '__none__'

type ConflictInfo = { message: string; blocked: boolean; conflicts: { control_code: string | null; keys: string[] }[] }

/**
 * 역할 일괄 배정 표 (2026-10-06) — 프로세스 행에서 기본값, 통제 행에서 예외. 여러 통제를 골라 한 번에 지정.
 * 변경은 모아 두었다가 "저장" 한 번으로 보낸다(`POST /api/org/assignments/bulk`). 겸직이 생기면 사유를 묻는다.
 * 역할 배정 메뉴와 RCM 화면이 같은 표를 쓴다.
 */
export default function RoleMatrix() {
  const tid = useActiveTenantId()
  const user = useAuthStore((s) => s.user)
  const canEdit = Boolean(user?.can_write) && isIcfrStaffForUser(user)
  const qc = useQueryClient()
  const { data, isLoading } = useQuery({
    queryKey: ['role-matrix', tid],
    queryFn: async () => (await apiClient.get<RoleMatrixData>('/api/org/role-matrix')).data,
  })
  const [pending, setPending] = useState<Pending>({})
  const [filter, setFilter] = useState<Filter>('all')
  const [q, setQ] = useState('')
  const [sel, setSel] = useState<Set<string>>(new Set())
  const [bulkRole, setBulkRole] = useState<RoleName>('control_owner')
  const [bulkUser, setBulkUser] = useState<string>('')
  const [conflict, setConflict] = useState<ConflictInfo | null>(null)
  const [reason, setReason] = useState('')

  const save = useMutation({
    mutationFn: async (conflict_reason?: string) =>
      (await apiClient.post<{ applied: number; removed: number; acknowledged: unknown[] }>('/api/org/assignments/bulk',
        { changes: toChanges(pending, data!), conflict_reason: conflict_reason || null })).data,
    onSuccess: (r) => {
      toast.success(`저장했습니다 — 지정 ${r.applied}건 · 해제 ${r.removed}건${r.acknowledged.length ? ` · 겸직 사유 ${r.acknowledged.length}건 기록` : ''}`)
      setPending({}); setSel(new Set()); setConflict(null); setReason('')
      void qc.invalidateQueries({ queryKey: ['role-matrix'] })
      void qc.invalidateQueries({ queryKey: ['assignments'] })
    },
    onError: (e) => {
      const d = (e as { response?: { data?: { detail?: ConflictInfo | string } } })?.response?.data?.detail
      if (d && typeof d === 'object' && d.conflicts?.length) setConflict(d)
      else toast.error(typeof d === 'string' ? d : (d as ConflictInfo | undefined)?.message ?? '저장하지 못했습니다')
    },
  })

  const procs = useMemo(() => new Map((data?.processes ?? []).map((p) => [p.id, p])), [data])
  const names = useMemo(() => new Map((data?.users ?? []).map((u) => [u.id, u.name])), [data])
  const groups = useMemo(() => data ? groupByProcess(data.controls.filter((c) => matches(c, filter, q)), data.processes) : [], [data, filter, q])
  const changes = data ? toChanges(pending, data) : []

  if (isLoading || !data) return <div className="flex items-center gap-2 p-6 text-muted-foreground"><Loader2 className="h-4 w-4 animate-spin" />불러오는 중…</div>

  const set = (k: string, v: string | null) => setPending((p) => ({ ...p, [k]: v }))
  const visibleIds = groups.flatMap((g) => g.controls.map((c) => c.id))
  const allSel = visibleIds.length > 0 && visibleIds.every((id) => sel.has(id))
  const applyBulk = () => {
    if (!bulkUser) return
    setPending((p) => {
      const n = { ...p }
      for (const id of sel) n[pkey('control', id, bulkRole)] = bulkUser === INHERIT ? null : bulkUser
      return n
    })
    toast.info(`${sel.size}개 통제의 ${ROLE_LABEL[bulkRole]}를 바꿨습니다 — "저장"을 눌러야 반영됩니다`)
  }

  const userOptions = (
    <>{data.users.map((u) => <option key={u.id} value={u.id}>{u.name}</option>)}</>
  )

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <div className="flex flex-wrap gap-1 rounded-md border p-1">
          {FILTERS.map((f) => (
            <Button key={f.v} size="sm" variant={filter === f.v ? 'default' : 'ghost'} onClick={() => setFilter(f.v)}>{f.label}</Button>
          ))}
        </div>
        <div className="relative w-56">
          <Search className="absolute left-2 top-2.5 h-3.5 w-3.5 text-muted-foreground" />
          <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="통제 코드·이름·문서상 수행자" className="h-9 pl-7 text-sm" />
        </div>
        <span className="ml-auto text-xs text-muted-foreground">
          프로세스 행 = 그 아래 통제의 <b>기본값</b> · 통제 행 = 그 통제만 <b>예외</b> · 회색은 기본값을 따르는 중
        </span>
      </div>

      {canEdit && sel.size > 0 && (
        <div className="sticky top-0 z-20 flex flex-wrap items-center gap-2 rounded-lg border border-primary/30 bg-accent px-3 py-2 text-sm shadow-card">
          <Users className="h-4 w-4 text-primary" />
          <span>선택한 통제 <b>{sel.size}</b>개의</span>
          <select value={bulkRole} onChange={(e) => setBulkRole(e.target.value as RoleName)} className="h-8 rounded-md border bg-background px-2 py-0">
            {ROLES.map((r) => <option key={r} value={r}>{ROLE_LABEL[r]}</option>)}
          </select>
          <span>를</span>
          <select value={bulkUser} onChange={(e) => setBulkUser(e.target.value)} className="h-8 min-w-36 rounded-md border bg-background px-2 py-0">
            <option value="">사람 선택</option>
            <option value={INHERIT}>프로세스 기본값 따름</option>
            {userOptions}
          </select>
          <Button size="sm" disabled={!bulkUser} onClick={applyBulk}>지정</Button>
          <Button size="sm" variant="ghost" onClick={() => setSel(new Set())}>선택 해제</Button>
        </div>
      )}

      <div className="max-h-[70vh] overflow-auto rounded-xl border bg-card shadow-card">
        <table className="w-full min-w-[920px] border-collapse text-sm">
          <thead className="sticky top-0 z-10 bg-card shadow-[0_1px_0_hsl(var(--border))]">
            <tr>
              {canEdit && (
                <th className="w-9 px-2 py-2">
                  <input type="checkbox" aria-label="보이는 통제 전체 선택" checked={allSel}
                    onChange={() => setSel(allSel ? new Set() : new Set(visibleIds))} />
                </th>
              )}
              <th className="px-3 py-2 text-left font-semibold">통제</th>
              {ROLES.map((r) => <th key={r} className="w-48 px-2 py-2 text-left font-semibold">{ROLE_LABEL[r]}</th>)}
            </tr>
          </thead>
          <tbody>
            {groups.map((g) => (
              <ProcessGroup key={g.process?.id ?? '-'} g={g} canEdit={canEdit} pending={pending} set={set}
                procs={procs} names={names} sel={sel} setSel={setSel} userOptions={userOptions} />
            ))}
            {groups.length === 0 && (
              <tr><td colSpan={canEdit ? 5 : 4} className="p-8 text-center text-muted-foreground">조건에 맞는 통제가 없습니다</td></tr>
            )}
          </tbody>
        </table>
      </div>

      {canEdit && changes.length > 0 && (
        <div className="sticky bottom-3 z-20 flex flex-wrap items-center gap-2 rounded-lg border bg-card px-4 py-2.5 shadow-lift">
          <span className="text-sm">저장하지 않은 변경 <b>{changes.length}</b>건</span>
          <Button size="sm" variant="ghost" className="ml-auto" onClick={() => setPending({})}><Undo2 className="mr-1.5 h-4 w-4" />되돌리기</Button>
          <Button size="sm" disabled={save.isPending} onClick={() => save.mutate(undefined)}>
            {save.isPending ? <Loader2 className="mr-1.5 h-4 w-4 animate-spin" /> : <Save className="mr-1.5 h-4 w-4" />}저장
          </Button>
        </div>
      )}

      <Dialog open={!!conflict} onOpenChange={(o) => { if (!o) setConflict(null) }}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2"><AlertTriangle className="h-5 w-5 text-amber-500" />겸직 조합이 생깁니다</DialogTitle>
            <DialogDescription>{conflict?.message}</DialogDescription>
          </DialogHeader>
          <ul className="max-h-40 overflow-auto rounded-md bg-muted px-3 py-2 text-sm">
            {conflict?.conflicts.map((c, i) => (
              <li key={i}><span className="font-mono">{c.control_code}</span> — {c.keys.map(conflictLabel).join(', ')}</li>
            ))}
          </ul>
          {conflict?.blocked ? (
            <p className="text-sm text-destructive">정책 설정에서 이 겸직을 금지하고 있어 저장할 수 없습니다. 사람을 바꾸거나 정책을 확인하세요.</p>
          ) : (
            <Textarea rows={3} value={reason} onChange={(e) => setReason(e.target.value)}
              placeholder="겸직 사유(보완통제) — 예: 관리 인원 4명으로 분리 불가, 팀장이 결과를 재검토" />
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setConflict(null)}>닫기</Button>
            {!conflict?.blocked && (
              <Button disabled={!reason.trim() || save.isPending} onClick={() => save.mutate(reason.trim())}>사유 남기고 저장</Button>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}

const conflictLabel = (k: string) => k.split('=').map((r) => ROLE_LABEL[r as RoleName] ?? (r === 'icfr_manager' ? '내부회계관리자' : r)).join(' = ')

function ProcessGroup({ g, canEdit, pending, set, procs, names, sel, setSel, userOptions }: {
  g: { process: RoleMatrixData['processes'][number] | null; controls: MatrixControl[] }
  canEdit: boolean
  pending: Pending
  set: (k: string, v: string | null) => void
  procs: Map<string, RoleMatrixData['processes'][number]>
  names: Map<string, string>
  sel: Set<string>
  setSel: (s: Set<string>) => void
  userOptions: React.ReactNode
}) {
  const p = g.process
  const ids = g.controls.map((c) => c.id)
  const allSel = ids.every((id) => sel.has(id))
  return (
    <>
      <tr className="border-y bg-muted/60">
        {canEdit && (
          <td className="px-2 py-1.5 text-center">
            <input type="checkbox" aria-label="이 프로세스 통제 전체 선택" checked={allSel}
              onChange={() => { const n = new Set(sel); ids.forEach((id) => (allSel ? n.delete(id) : n.add(id))); setSel(n) }} />
          </td>
        )}
        <td className="px-3 py-1.5 font-semibold">
          {p ? <><span className="font-mono text-xs text-muted-foreground">{p.code}</span> {p.name}</> : '프로세스 없음'}
          <span className="ml-2 text-xs font-normal text-muted-foreground">통제 {g.controls.length} · 기본값</span>
        </td>
        {ROLES.map((r) => {
          if (!p) return <td key={r} />
          const k = pkey('process', p.id, r)
          const v = k in pending ? pending[k] : p.roles[r]?.user_id ?? null
          return (
            <td key={r} className="px-2 py-1.5">
              <select disabled={!canEdit} value={v ?? NONE} onChange={(e) => set(k, e.target.value === NONE ? null : e.target.value)}
                className={cn('h-8 w-full rounded-md border bg-background px-2 py-0 font-medium', k in pending && 'border-amber-400 bg-amber-50 dark:bg-amber-950/30')}>
                <option value={NONE}>— 미지정 —</option>
                {userOptions}
              </select>
            </td>
          )
        })}
      </tr>
      {g.controls.map((c) => (
        <tr key={c.id} className={cn('border-b hover:bg-muted/30', sel.has(c.id) && 'bg-accent/50')}>
          {canEdit && (
            <td className="px-2 py-1 text-center">
              <input type="checkbox" aria-label={`${c.code} 선택`} checked={sel.has(c.id)}
                onChange={() => { const n = new Set(sel); if (n.has(c.id)) n.delete(c.id); else n.add(c.id); setSel(n) }} />
            </td>
          )}
          <td className="px-3 py-1">
            <div className="flex items-center gap-1.5">
              <span className="font-mono text-xs text-muted-foreground">{c.code}</span>
              {c.is_key_control && <Star className="h-3 w-3 fill-amber-400 text-amber-500" aria-label="핵심통제" />}
              {/* IUC(통제에 쓰는 정보) 안에 EUC(스프레드시트)가 포함된다 — 따로 세면 같은 것을 두 번 보인다 */}
              {c.iuc_count > 0 && (
                <Badge variant="outline" className="px-1 text-[10px]" title="통제에 쓰는 정보(IUC) 수 · 그중 사용자 스프레드시트(EUC)">
                  IUC {c.iuc_count}{c.euc_count > 0 ? ` (EUC ${c.euc_count})` : ''}
                </Badge>
              )}
              {c.conflicts.length > 0 && <Badge variant="outline" className="border-amber-400 px-1 text-[10px] text-amber-700">겸직</Badge>}
            </div>
            <p className="line-clamp-1" title={c.name ?? ''}>{c.name}</p>
            {c.owner_name && <p className="text-xs text-muted-foreground">문서상 수행자: {c.owner_name}</p>}
          </td>
          {ROLES.map((r) => {
            const k = pkey('control', c.id, r)
            const e = effective(c, r, pending, procs)
            const inheritName = e.overridden ? null : (e.userId ? names.get(e.userId) : null)
            return (
              <td key={r} className="px-2 py-1">
                <select disabled={!canEdit} value={e.overridden ? (e.userId ?? INHERIT) : INHERIT}
                  onChange={(ev) => set(k, ev.target.value === INHERIT ? null : ev.target.value)}
                  className={cn('h-8 w-full rounded-md border bg-background px-2 py-0',
                    !e.overridden && 'text-muted-foreground', k in pending && 'border-amber-400 bg-amber-50 dark:bg-amber-950/30')}>
                  <option value={INHERIT}>
                    {inheritName ? `기본값 · ${inheritName}${e.source === 'derived' ? '(부서장)' : ''}` : r === 'dept_approver' ? '부서장 자동' : '— 미지정 —'}
                  </option>
                  {userOptions}
                </select>
              </td>
            )
          })}
        </tr>
      ))}
    </>
  )
}
