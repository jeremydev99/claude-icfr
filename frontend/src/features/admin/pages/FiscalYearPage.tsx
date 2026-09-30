import { useEffect, useMemo, useState } from 'react'
import { toast } from 'sonner'
import { Loader2, Lock } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { useAuthStore } from '@/features/auth/store'
import { isIcfrManagerForUser } from '@/features/auth/permissions.pure'
import { errorDetail, usePeriodSuggestion, usePolicies, useUpsertPolicy } from '../api/PolicyAssignmentApi'
import {
  POLICY_FISCAL_YEAR_START_MONTH,
  describeFiscalYear,
  parseStartMonth,
  policyMap,
} from '../PolicyDefs.pure'

const MONTHS = Array.from({ length: 12 }, (_, i) => i + 1)
const FREQUENCIES = [
  { value: 'annual', label: '연간' },
  { value: 'semiannual', label: '반기' },
  { value: 'quarterly', label: '분기' },
  { value: 'monthly', label: '월' },
] as const

function SuggestionRow({ frequency, label }: { frequency: string; label: string }) {
  const { data, isLoading, isError } = usePeriodSuggestion(frequency)
  return (
    <TableRow>
      <TableCell>{label}</TableCell>
      {isLoading ? (
        <TableCell colSpan={3} className="text-muted-foreground">
          불러오는 중…
        </TableCell>
      ) : isError || !data ? (
        <TableCell colSpan={3} className="text-destructive">
          제안값을 불러오지 못했습니다
        </TableCell>
      ) : (
        <>
          <TableCell>FY{data.fiscal_year}</TableCell>
          <TableCell>{data.period_index}회차</TableCell>
          <TableCell className="font-mono text-xs">
            {data.period_start} ~ {data.period_end}
          </TableCell>
        </>
      )}
    </TableRow>
  )
}

export default function FiscalYearPage() {
  const { user } = useAuthStore()
  const canManage = isIcfrManagerForUser(user)
  const { data, isLoading } = usePolicies()
  const upsert = useUpsertPolicy()

  const raw = useMemo(() => policyMap(data?.items)[POLICY_FISCAL_YEAR_START_MONTH], [data])
  const current = parseStartMonth(raw)
  const [draft, setDraft] = useState(String(current))
  useEffect(() => setDraft(String(current)), [current])

  const save = async () => {
    try {
      await upsert.mutateAsync({ policy_key: POLICY_FISCAL_YEAR_START_MONTH, policy_value: draft })
      toast.success('회계연도 시작월을 저장했습니다')
    } catch (e) {
      toast.error(errorDetail(e, '저장하지 못했습니다'))
    }
  }

  return (
    <div className="space-y-4 p-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">회계연도 시작월</h1>
          <p className="text-sm text-muted-foreground">
            결산월이 아니라 <strong>시작월</strong>입니다. 12월 결산 회사는 1, 3월 결산 회사는 4입니다.
          </p>
        </div>
        {!canManage && (
          <Badge variant="outline">
            <Lock className="mr-1 h-3 w-3" /> 읽기 전용 · 내부회계관리자만 편집
          </Badge>
        )}
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">설정</CardTitle>
          <p className="text-sm text-muted-foreground">
            평가 회차를 만들 때 기간 제안값이 이 값을 기준으로 계산됩니다. 제안일 뿐 강제하지 않으며, 회차 생성 시
            담당자가 조정할 수 있습니다.
          </p>
        </CardHeader>
        <CardContent className="space-y-3">
          {isLoading ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <>
              <div className="flex flex-wrap items-end gap-2">
                <div className="space-y-1">
                  <Label htmlFor="fy-start">시작월</Label>
                  <Select value={draft} onValueChange={setDraft} disabled={!canManage}>
                    <SelectTrigger id="fy-start" className="w-32">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {MONTHS.map((m) => (
                        <SelectItem key={m} value={String(m)}>
                          {m}월
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                {canManage && (
                  <Button onClick={save} disabled={draft === String(current) || upsert.isPending}>
                    {upsert.isPending && <Loader2 className="mr-1 h-4 w-4 animate-spin" />}
                    저장
                  </Button>
                )}
                {raw === undefined && <Badge variant="secondary">미설정 · 기본값 1월</Badge>}
              </div>
              <p className="text-sm">
                회계연도: <strong>{describeFiscalYear(Number(draft))}</strong>
              </p>
            </>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">현재 기간 제안값 (저장된 설정 기준)</CardTitle>
          <p className="text-sm text-muted-foreground">오늘이 속한 회계연도·회차에 대해 서버가 제안하는 평가 대상 기간입니다.</p>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>주기</TableHead>
                  <TableHead>회계연도</TableHead>
                  <TableHead>회차</TableHead>
                  <TableHead>기간</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {FREQUENCIES.map((f) => (
                  <SuggestionRow key={f.value} frequency={f.value} label={f.label} />
                ))}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
