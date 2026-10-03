import EmptyState from '@/components/illustration/EmptyState'
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { Loader2 } from 'lucide-react'
import apiClient from '@/lib/axios'
import { useActiveTenantId } from '@/features/auth/store'
import { Badge } from '@/components/ui/badge'
import { coverageTone, coverageRate, type ScopingCoverage } from '../coverage.pure'

/**
 * 유의 계정 ↔ RCM 통제 커버리지 (초안, 2026-10-03) — `GET /api/scoping/{id}/coverage`.
 *
 * RCM 의 관련 계정은 자유 텍스트라 **이름 대조로 추정**한다(서버 `services/scoping_coverage.py`).
 * 확정 판정이 아니라 "통제가 없는 유의 계정"을 찾는 검토 출발점이다.
 */
export default function CoverageSection({ scopingId }: { scopingId: string }) {
  const tenantId = useActiveTenantId()
  const [showAll, setShowAll] = useState(false)
  const { data, isLoading, isError } = useQuery({
    queryKey: ['scoping-coverage', tenantId, scopingId],
    queryFn: async () => (await apiClient.get<ScopingCoverage>(`/api/scoping/${scopingId}/coverage`)).data,
    staleTime: 0,
  })

  if (isLoading) {
    return <div className="flex items-center gap-2 p-4 text-sm text-muted-foreground"><Loader2 className="h-4 w-4 animate-spin" /> 커버리지 계산 중…</div>
  }
  if (isError || !data) return <div className="p-4 text-sm text-destructive">커버리지를 불러오지 못했습니다</div>

  const rows = showAll ? data.accounts : data.accounts.filter((a) => !a.covered || !a.key_covered)
  const rate = coverageRate(data)

  return (
    <section className="space-y-3">
      <div className="text-xs text-muted-foreground">
        <Badge variant="outline" className="mr-1 align-middle">추정</Badge>
        유의 계정마다 RCM 통제의 관련 계정 텍스트와 계정명을 대조한 결과입니다 — 최종 판단은 담당자가 합니다
      </div>

      {data.significant_total === 0 ? (
        <EmptyState
          compact
          slot="empty-finance"
          title="유의한 계정(최종 결론 Y)이 아직 없습니다"
          description="중요성 기준과 질적 평가를 입력하면 계산됩니다."
        />
      ) : (
        <>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-sm">
            <Stat label="유의 계정" value={data.significant_total} />
            <Stat label="통제 있음" value={`${data.covered} (${rate}%)`} tone={coverageTone(data)} />
            <Stat label="통제 없음" value={data.uncovered} tone={data.uncovered ? 'bad' : 'ok'} />
            <Stat label="핵심통제 있음" value={data.key_covered} />
          </div>
          <p className="text-xs text-muted-foreground">
            RCM 통제 {data.control_total}개 중 전사 통제("전 계정") {data.entity_level_controls}개는 특정 계정 커버로 세지 않았습니다.
          </p>

          <div className="flex items-center justify-between text-sm">
            <span className="font-medium">{showAll ? '전체 유의 계정' : '확인이 필요한 계정 (통제 없음 · 핵심통제 없음)'}</span>
            <label className="flex items-center gap-1.5 text-xs">
              <input type="checkbox" checked={showAll} onChange={(e) => setShowAll(e.target.checked)} /> 전체 보기
            </label>
          </div>
          {rows.length === 0 ? (
            <p className="text-sm text-green-700">모든 유의 계정에 핵심통제가 대응합니다.</p>
          ) : (
            <ul className="divide-y rounded-md border text-sm">
              {rows.map((a) => (
                <li key={`${a.statement_type}-${a.name}`} className="flex flex-wrap items-start gap-2 px-3 py-2">
                  <Badge variant="outline" className="shrink-0">{a.statement_type}</Badge>
                  <span className="font-medium min-w-[8rem]">{a.name}</span>
                  {a.covered ? (
                    <span className="flex flex-wrap gap-1">
                      {a.controls.slice(0, 6).map((c) => (
                        <Badge key={c.code ?? c.name} variant="outline"
                          className={c.match === 'exact' ? 'border-green-300 text-green-800' : 'border-gray-300 text-gray-600'}
                          title={`${c.name ?? ''}${c.is_key_control ? ' · 핵심통제' : ''} · ${c.match === 'exact' ? '이름 일치' : '부분 일치'}`}>
                          {c.code}{c.is_key_control ? ' ★' : ''}
                        </Badge>
                      ))}
                      {a.controls.length > 6 && <span className="text-xs text-muted-foreground">외 {a.controls.length - 6}개</span>}
                    </span>
                  ) : (
                    <span className="text-red-700">대응 통제 없음 — <Link to="/rcm" className="underline">RCM</Link>에서 통제의 관련 계정을 확인하세요</span>
                  )}
                </li>
              ))}
            </ul>
          )}
        </>
      )}

      {data.unmatched_rcm_tokens.length > 0 && (
        <details className="text-sm">
          <summary className="cursor-pointer text-muted-foreground">
            RCM 관련 계정 중 스코핑 계정과 이름이 맞지 않는 표기 {data.unmatched_rcm_tokens.length}개 (오타·명칭 차이 점검)
          </summary>
          <ul className="mt-2 grid gap-1 sm:grid-cols-2">
            {data.unmatched_rcm_tokens.map((u) => (
              <li key={u.token} className="text-xs">
                <span className="font-mono">{u.token}</span> <span className="text-muted-foreground">— {u.control_codes.slice(0, 4).join(', ')}{u.control_codes.length > 4 ? ' …' : ''}</span>
              </li>
            ))}
          </ul>
        </details>
      )}
    </section>
  )
}

function Stat({ label, value, tone }: { label: string; value: number | string; tone?: 'ok' | 'warn' | 'bad' }) {
  const color = tone === 'bad' ? 'text-red-700' : tone === 'warn' ? 'text-amber-700' : tone === 'ok' ? 'text-green-700' : ''
  return (
    <div className="rounded-md border px-3 py-2">
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className={`text-lg font-semibold ${color}`}>{value}</div>
    </div>
  )
}
