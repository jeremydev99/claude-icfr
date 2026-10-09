import { useEffect, useMemo, useState } from 'react'
import { toast } from 'sonner'
import { Loader2, Lock } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import HelpButton from '@/features/help/HelpButton'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { useAuthStore } from '@/features/auth/store'
import { isIcfrManagerForUser } from '@/features/auth/permissions.pure'
import { errorDetail, usePeriodSuggestion, usePolicies, useUpsertPolicy } from '../api/PolicyAssignmentApi'
import { POLICY_FISCAL_YEAR_START_MONTH, parseStartMonth, policyMap } from '../PolicyDefs.pure'
import { describeClose, endMonthOf, fiscalYearOfDate, fyLabel, fyShort, startMonthOf } from '@/lib/fiscalYear'

const MONTHS = Array.from({ length: 12 }, (_, i) => i + 1)
const FREQUENCIES = [
  { value: 'annual', label: '연간' },
  { value: 'semiannual', label: '반기' },
  { value: 'quarterly', label: '분기' },
  { value: 'monthly', label: '월' },
] as const

function SuggestionRow({ frequency, label, startMonth }: { frequency: string; label: string; startMonth: number }) {
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
          <TableCell>{fyShort(data.fiscal_year, startMonth)}</TableCell>
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
  // 화면은 결산월로 묻고(국내 실무 표현), 저장은 종전대로 시작월(= 결산월 다음 달)로 한다 — lib/fiscalYear
  const currentEnd = endMonthOf(current)
  const [draft, setDraft] = useState(String(currentEnd))
  useEffect(() => setDraft(String(currentEnd)), [currentEnd])
  const draftStart = startMonthOf(Number(draft))
  const thisFy = fiscalYearOfDate(new Date(), draftStart)

  const save = async () => {
    try {
      await upsert.mutateAsync({ policy_key: POLICY_FISCAL_YEAR_START_MONTH, policy_value: String(draftStart) })
      toast.success(`${draft}월 결산으로 저장했습니다`)
    } catch (e) {
      toast.error(errorDetail(e, '저장하지 못했습니다'))
    }
  }

  return (
    <div className="mx-auto max-w-[1400px] space-y-6 p-6 md:p-8">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">회계연도 · 결산월</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            회사의 <strong>결산월</strong>을 고르세요. 회계연도는 결산월 다음 달 1일부터 1년입니다.
            <strong> &lsquo;N 회계연도&rsquo;는 N년에 시작하는 회계연도</strong>입니다 — 화면 곳곳에 기간을 함께 표시합니다.
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
          <CardTitle className="flex items-center gap-1 text-base">설정<HelpButton k="screen.admin.fiscal-year.settings" /></CardTitle>
          <p className="text-sm text-muted-foreground">
            평가 회차 기간, 일정 날짜, 재무제표 업로드의 회계연도 판단, 보고서 기준일(회계연도 말일)이 이 값으로 정해집니다.
            회차 기간은 제안일 뿐 회차를 만들 때 조정할 수 있습니다.
          </p>
        </CardHeader>
        <CardContent className="space-y-3">
          {isLoading ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <>
              <div className="flex flex-wrap items-end gap-2">
                <div className="space-y-1">
                  <Label htmlFor="fy-start">결산월</Label>
                  <Select value={draft} onValueChange={setDraft} disabled={!canManage}>
                    <SelectTrigger id="fy-start" className="w-32">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {MONTHS.map((m) => (
                        <SelectItem key={m} value={String(m)}>
                          {m}월 결산
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                {canManage && (
                  <Button onClick={save} disabled={draft === String(currentEnd) || upsert.isPending}>
                    {upsert.isPending && <Loader2 className="mr-1 h-4 w-4 animate-spin" />}
                    저장
                  </Button>
                )}
                {raw === undefined && <Badge variant="secondary">미설정 · 기본값 12월 결산</Badge>}
              </div>
              <div className="space-y-1 rounded-lg border bg-muted/40 px-3 py-2 text-sm">
                <p>{describeClose(Number(draft))}</p>
                <p>올해 기준: <strong>{fyLabel(thisFy, draftStart)}</strong></p>
                <p className="text-xs text-muted-foreground">
                  예) 3월 결산이면 2026 회계연도 = 2026.04.01 ~ 2027.03.31. 재무제표의 &lsquo;2027년 3월 31일 현재&rsquo;는 2026 회계연도로 읽습니다.
                </p>
              </div>
            </>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-1 text-base">현재 기간 제안값 (저장된 설정 기준)<HelpButton k="screen.admin.fiscal-year.suggestions" /></CardTitle>
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
                  <SuggestionRow key={f.value} frequency={f.value} label={f.label} startMonth={current} />
                ))}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
