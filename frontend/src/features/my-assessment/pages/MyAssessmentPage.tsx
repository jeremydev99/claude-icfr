import { useEffect, useMemo, useState } from 'react'
import { AlertTriangle, Loader2 } from 'lucide-react'
import { useAuthStore } from '@/features/auth/store'
import { canViewAllForUser } from '@/features/auth/permissions.pure'
import { useCycles } from '@/features/schedule/api/useSchedule'
import { Badge } from '@/components/ui/badge'
import { Checkbox } from '@/components/ui/checkbox'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { useWorklist } from '../api'
import ActivitySheet from '../components/ActivitySheet'
import { Button } from '@/components/ui/button'
import {
  FREQ_LABEL,
  KIND_LABEL,
  matchesOwner,
  matchesRole,
  OWNER_ALL,
  OWNER_NONE,
  ownerOptions,
  progressText,
  ROLE_FILTER_LABEL,
  ROLE_LABEL,
  type RoleFilter,
  STAGE_LABEL,
  STATE_LABEL,
  STATE_VARIANT,
  summarize,
} from '../myAssessment.pure'

/**
 * 내 평가(2026-10-15) — 평가 회차의 대상 통제 중 **RCM 역할 배정으로 내가 맡은 것**이 자동으로 나온다.
 * 통제를 하나씩 등록하지 않는다. 통제를 누르면 테스트 기록 + 샘플별 증빙을 한 화면에서 작성·제출한다.
 * 필요 샘플 수: 설계평가 1, 운영평가 RCM 표본수(감사인 협의 값). 적게는 제출할 수 없다.
 */
export default function MyAssessmentPage() {
  const user = useAuthStore((s) => s.user)
  // 전체 보기 — 서버 `FULL_VIEW_ROLES` 와 같은 판정, 최종은 서버 403
  const canFullView = canViewAllForUser(user)
  const [kind, setKind] = useState<'operation' | 'design'>('operation')
  const [cycleId, setCycleId] = useState<string | null>(null)
  const [full, setFull] = useState(false)
  const [selected, setSelected] = useState<string | null>(null)

  const { data: allCycles = [], isLoading: cyclesLoading } = useCycles()
  const cycles = useMemo(() => allCycles.filter((c) => c.kind === kind), [allCycles, kind])
  useEffect(() => {
    if (!cycles.some((c) => c.id === cycleId)) {
      setCycleId((cycles.find((c) => c.status === 'open') ?? cycles[0])?.id ?? null)
    }
  }, [cycles, cycleId])
  const cycle = cycles.find((c) => c.id === cycleId) ?? null

  const showFull = full && canFullView
  const { data: allRows = [], isLoading, isError } = useWorklist(cycleId, !showFull)
  // 내 담당: 작성할 것(통제책임자)·승인할 것(평가자·부서승인자). 작성할 것이 있으면 그것부터 보인다
  const [roleFilter, setRoleFilter] = useState<RoleFilter | null>(null)
  const roleCounts = useMemo(() => ({
    write: allRows.filter((r) => matchesRole(r, 'write')).length,
    approve: allRows.filter((r) => matchesRole(r, 'approve')).length,
    all: allRows.length,
  }), [allRows])
  const role: RoleFilter = roleFilter ?? (roleCounts.write > 0 ? 'write' : 'all')
  // 전체 보기: 통제책임자 고르기
  const [owner, setOwner] = useState(OWNER_ALL)
  const owners = useMemo(() => ownerOptions(allRows), [allRows])
  const unassignedCount = allRows.filter((r) => !r.owner_id).length
  const rows = showFull ? allRows.filter((r) => matchesOwner(r, owner)) : allRows.filter((r) => matchesRole(r, role))
  const sum = summarize(rows)
  const row = allRows.find((r) => r.control_id === selected) ?? null

  return (
    <div className="mx-auto max-w-[1400px] space-y-6 p-6 md:p-8">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">내 평가</h1>
        <p className="text-sm text-muted-foreground">
          RCM 역할 배정으로 내가 맡은 통제가 자동으로 나옵니다. 통제를 눌러 테스트를 기록하고 샘플마다 증빙을 올리세요.
        </p>
      </div>

      <div className="flex flex-wrap items-end gap-4">
        <Tabs value={kind} onValueChange={(v) => { setKind(v as 'operation' | 'design'); setSelected(null) }}>
          <TabsList>
            <TabsTrigger value="operation">운영평가</TabsTrigger>
            <TabsTrigger value="design">설계평가</TabsTrigger>
          </TabsList>
        </Tabs>
        <div className="space-y-1">
          <Label>평가 회차</Label>
          <Select value={cycleId ?? ''} onValueChange={(v) => { setCycleId(v); setSelected(null) }} disabled={cycles.length === 0}>
            <SelectTrigger className="w-72"><SelectValue placeholder={`${KIND_LABEL[kind]} 회차 없음`} /></SelectTrigger>
            <SelectContent>
              {cycles.map((c) => (
                <SelectItem key={c.id} value={c.id}>{c.name}{c.status !== 'open' ? ' (마감)' : ''}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        {showFull ? (
          <div className="space-y-1">
            <Label>통제책임자</Label>
            <Select value={owner} onValueChange={setOwner}>
              <SelectTrigger className="w-56"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value={OWNER_ALL}>전체 ({allRows.length})</SelectItem>
                {owners.map((o) => <SelectItem key={o.id} value={o.id}>{o.name} ({o.count})</SelectItem>)}
                {unassignedCount > 0 && <SelectItem value={OWNER_NONE}>미배정 ({unassignedCount})</SelectItem>}
              </SelectContent>
            </Select>
          </div>
        ) : (
          cycle && allRows.length > 0 && (
            <div className="flex gap-1" role="group" aria-label="내 역할로 거르기">
              {(['write', 'approve', 'all'] as const).map((f) => (
                <Button key={f} size="sm" variant={role === f ? 'default' : 'outline'} onClick={() => setRoleFilter(f)}>
                  {ROLE_FILTER_LABEL[f]} {roleCounts[f]}
                </Button>
              ))}
            </div>
          )
        )}
        {canFullView && (
          <label className="mb-2 flex items-center gap-2 text-sm">
            <Checkbox checked={full} onCheckedChange={(v) => { setFull(Boolean(v)); setOwner(OWNER_ALL) }} />전체 통제 보기
          </label>
        )}
      </div>

      {!cyclesLoading && cycles.length === 0 && (
        <p className="text-sm text-muted-foreground">
          {KIND_LABEL[kind]} 회차가 없습니다. 회차는 평가자(전담부서)가 일정관리에서 만듭니다.
        </p>
      )}

      {cycle && (
        <div className="flex flex-wrap gap-2 text-sm">
          <Badge variant="outline">대상 {sum.total}</Badge>
          {(['not_started', 'draft', 'submitted', 'approved'] as const).map((s) => (
            <Badge key={s} variant={STATE_VARIANT[s]}>{STATE_LABEL[s]} {sum.by[s]}</Badge>
          ))}
          <Badge variant="outline">필요 샘플 {sum.samples}건</Badge>
          {cycle.status !== 'open' && <Badge variant="destructive">마감된 회차 — 조회만</Badge>}
        </div>
      )}

      {showFull && unassignedCount > 0 && (
        <p className="flex items-center gap-1 text-sm text-amber-700">
          <AlertTriangle className="h-4 w-4" />통제책임자가 배정되지 않은 통제 {unassignedCount}건 — 역할 배정에서 지정해야 작성할 수 있습니다.
        </p>
      )}

      {isLoading && <Loader2 className="h-5 w-5 animate-spin" />}
      {isError && <p className="text-sm text-destructive">목록을 불러오지 못했습니다.</p>}
      {cycle && !isLoading && !isError && rows.length === 0 && (
        <p className="text-sm text-muted-foreground">{allRows.length === 0 ? '이 회차에서 내가 맡은 통제가 없습니다.' : '이 조건에 맞는 통제가 없습니다.'}</p>
      )}

      {rows.length > 0 && (
        <div className="rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-36">통제</TableHead>
                <TableHead>통제명</TableHead>
                <TableHead className="w-16">주기</TableHead>
                <TableHead className="w-32">{showFull ? '통제책임자' : '내 역할'}</TableHead>
                <TableHead className="w-24">샘플</TableHead>
                <TableHead className="w-16">증빙</TableHead>
                <TableHead className="w-40">상태</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((r) => (
                <TableRow key={r.control_id} className="cursor-pointer" onClick={() => setSelected(r.control_id)}>
                  <TableCell className="font-mono text-xs">{r.control_code}</TableCell>
                  <TableCell>{r.control_name}</TableCell>
                  <TableCell>{FREQ_LABEL[r.frequency ?? ''] ?? '-'}</TableCell>
                  <TableCell>
                    {showFull
                      ? (r.owner_name ?? <span className="text-amber-700">미배정</span>)
                      : r.my_roles.map((x) => ROLE_LABEL[x] ?? x).join(', ')}
                  </TableCell>
                  <TableCell title={r.sample_basis}>{progressText(r)}</TableCell>
                  <TableCell>{r.evidence_count}</TableCell>
                  <TableCell className="space-x-1">
                    <Badge variant={STATE_VARIANT[r.state]}>{STATE_LABEL[r.state]}</Badge>
                    {r.can_approve.length > 0 && (
                      <Badge variant="destructive">{r.can_approve.map((s) => STAGE_LABEL[s] ?? s).join('·')} 필요</Badge>
                    )}
                    {r.sod_blocked && <Badge variant="outline" title={r.sod_blocked}>직무분리 — 다른 승인자 필요</Badge>}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      {cycle && (
        <ActivitySheet cycleId={cycle.id} cycleOpen={cycle.status === 'open'} row={row} onClose={() => setSelected(null)} />
      )}
    </div>
  )
}
