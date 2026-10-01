import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Loader2 } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { fetchLoginEvents } from '../api/usersApi'
import { describeDevice, LOGIN_REASON_LABEL } from '../loginEvents.pure'

/** 로그인 시도 기록 (보안 1단계, 관리자 전용) — 성공·실패·잠김을 IP·기기와 함께 최신순으로 본다. */
export default function LoginEventsTable() {
  const [failedOnly, setFailedOnly] = useState(false)
  const { data = [], isLoading, isError } = useQuery({
    queryKey: ['login-events', failedOnly],
    queryFn: () => fetchLoginEvents({ failed_only: failedOnly, limit: 300 }),
    staleTime: 30_000,
  })

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between text-sm">
        <span className="text-muted-foreground">최근 {data.length}건 · 같은 IP 에서 분당 10회를 넘는 시도는 서버가 먼저 차단합니다</span>
        <label className="flex items-center gap-1.5">
          <input type="checkbox" checked={failedOnly} onChange={(e) => setFailedOnly(e.target.checked)} />
          실패만
        </label>
      </div>
      {isLoading ? (
        <div className="flex items-center justify-center p-12 text-muted-foreground gap-2">
          <Loader2 className="h-5 w-5 animate-spin" /> 불러오는 중...
        </div>
      ) : isError ? (
        <div className="rounded-md border p-8 text-center text-sm text-destructive">로그인 기록을 불러오지 못했습니다 (관리자 전용)</div>
      ) : data.length === 0 ? (
        <div className="rounded-md border p-12 text-center text-sm text-muted-foreground">기록이 없습니다.</div>
      ) : (
        <div className="rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>시각</TableHead>
                <TableHead>이메일</TableHead>
                <TableHead>결과</TableHead>
                <TableHead>IP</TableHead>
                <TableHead>기기</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.map((e) => (
                <TableRow key={e.id}>
                  <TableCell className="text-sm whitespace-nowrap">{new Date(e.created_at).toLocaleString('ko-KR')}</TableCell>
                  <TableCell className="text-sm">{e.email}</TableCell>
                  <TableCell>
                    <Badge variant="outline" className={e.success ? 'bg-green-50 text-green-700 border-green-200' : 'bg-red-50 text-red-700 border-red-200'}>
                      {LOGIN_REASON_LABEL[e.reason] ?? e.reason}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-sm font-mono">{e.ip ?? '-'}</TableCell>
                  <TableCell className="text-sm text-muted-foreground">{describeDevice(e.user_agent)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  )
}
