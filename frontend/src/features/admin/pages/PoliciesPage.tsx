import { useMemo } from 'react'
import { Link } from 'react-router-dom'
import { Loader2, Lock } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import HelpButton from '@/features/help/HelpButton'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { useAuthStore } from '@/features/auth/store'
import { isIcfrManagerForUser } from '@/features/auth/permissions.pure'
import { usePolicies } from '../api/PolicyAssignmentApi'
import {
  POLICY_FISCAL_YEAR_START_MONTH,
  POLICY_GROUPS,
  parseStartMonth,
  policyMap,
  unknownPolicies,
} from '../PolicyDefs.pure'
import PolicyField from '../components/PolicyField'

/** 정책 묶음 제목 → 도움말 항목 */
const GROUP_HELP: Record<string, string> = {
  '평가 워크플로': 'screen.admin.policies.workflow',
  '이해상충(겸직) 조합': 'screen.admin.policies.conflict',
  '증빙': 'screen.admin.policies.evidence',
  'EUC · 스코핑 기본값': 'screen.admin.policies.euc-scoping',
}

export default function PoliciesPage() {
  const { user } = useAuthStore()
  const canManage = isIcfrManagerForUser(user)
  const { data, isLoading, isError } = usePolicies()
  const values = useMemo(() => policyMap(data?.items), [data])
  const unknown = useMemo(() => unknownPolicies(data?.items), [data])

  return (
    <div className="mx-auto max-w-[1400px] space-y-6 p-6 md:p-8">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">정책 설정</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            테넌트 단위 운영 정책입니다. 설정하지 않은 항목은 서버 기본값을 따릅니다.
          </p>
        </div>
        {!canManage && (
          <Badge variant="outline">
            <Lock className="mr-1 h-3 w-3" /> 읽기 전용 · 내부회계관리자만 편집
          </Badge>
        )}
      </div>

      {isLoading ? (
        <div className="flex items-center gap-2 py-8 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" /> 불러오는 중…
        </div>
      ) : isError ? (
        <p className="py-8 text-sm text-destructive">정책을 불러오지 못했습니다.</p>
      ) : (
        <>
          <Card>
            <CardContent className="flex flex-wrap items-center justify-between gap-2 pt-6 text-sm">
              <span>
                회계연도 시작월: <strong>{parseStartMonth(values[POLICY_FISCAL_YEAR_START_MONTH])}월</strong>
              </span>
              <Link to="/admin/fiscal-year" className="text-primary underline-offset-4 hover:underline">
                회계연도 화면에서 변경 →
              </Link>
            </CardContent>
          </Card>

          {POLICY_GROUPS.map((g) => (
            <Card key={g.title}>
              <CardHeader className="pb-2">
                <CardTitle className="flex items-center gap-1 text-base">{g.title}{GROUP_HELP[g.title] && <HelpButton k={GROUP_HELP[g.title]} />}</CardTitle>
              </CardHeader>
              <CardContent>
                {g.defs.map((d) => (
                  <PolicyField key={d.key} def={d} raw={values[d.key]} canEdit={canManage} />
                ))}
              </CardContent>
            </Card>
          ))}

          {unknown.length > 0 && (
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-base">기타 저장된 정책 (화면 미지원 · 읽기 전용)</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="overflow-x-auto">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>키</TableHead>
                        <TableHead>값</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {unknown.map((p) => (
                        <TableRow key={p.policy_key}>
                          <TableCell className="font-mono text-xs">{p.policy_key}</TableCell>
                          <TableCell className="font-mono text-xs">{p.policy_value}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              </CardContent>
            </Card>
          )}
        </>
      )}
    </div>
  )
}
