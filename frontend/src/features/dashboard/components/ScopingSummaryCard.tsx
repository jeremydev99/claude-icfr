import { Link } from 'react-router-dom'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { useScopingMeta, useScopingSummary } from '@/features/scoping/api/useScoping'

const won = (v: number | null) => (v === null ? '—' : v.toLocaleString('ko-KR'))

/**
 * 대시보드 스코핑 카드 (6-1) — 가장 최근 회계연도.
 *
 * **미평가를 따로 센다.** 금액을 넣지 않았거나 질적 요소가 비면 "유의하지 않음"이 아니라 미평가다 —
 * N 과 섞으면 평가하지 않은 계정이 범위 밖으로 빠진 것처럼 읽힌다.
 */
export default function ScopingSummaryCard() {
  const { data } = useScopingSummary()
  const { data: meta } = useScopingMeta()
  const label = (s: string | null) => meta?.statuses.find((x) => x.value === s)?.label ?? s ?? '—'

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex flex-wrap items-baseline gap-3">
          <Link to="/scoping" className="hover:underline">Scoping</Link>
          {data?.exists && (
            <span className="text-sm font-normal text-muted-foreground">
              {data.fiscal_year} 회계연도 · {label(data.status)} · 템플릿 그대로인 필드 {data.badge_count}개
            </span>
          )}
        </CardTitle>
      </CardHeader>
      <CardContent>
        {data && !data.exists && (
          <p className="text-sm text-muted-foreground">아직 스코핑이 없습니다 — 회계연도를 만들면 표준 템플릿이 복사됩니다.</p>
        )}
        {data?.exists && meta && (
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-5">
            <div className="rounded-md border p-3">
              <h3 className="-m-3 mb-2 rounded-t-md border-b border-amber-100 bg-amber-50 px-3 py-2 text-sm font-semibold text-amber-900">
                중요성
              </h3>
              <ul className="space-y-1 text-sm">
                <li className="flex justify-between"><span>전반중요성</span><span className="tabular-nums">{won(data.overall_materiality)}</span></li>
                <li className="flex justify-between"><span>수행중요성</span><span className="tabular-nums">{won(data.smt)}</span></li>
              </ul>
            </div>
            {meta.statement_types.map((t) => {
              const c = data.by_statement[t.value] ?? { Y: 0, N: 0, unevaluated: 0 }
              return (
                <div key={t.value} className="rounded-md border p-3">
                  <h3 className="-m-3 mb-2 rounded-t-md border-b border-blue-100 bg-blue-50 px-3 py-2 text-sm font-semibold text-blue-900">
                    {t.label}
                  </h3>
                  <ul className="space-y-1 text-sm">
                    <li className="flex justify-between"><span>유의</span><span className="tabular-nums font-medium">{c.Y}</span></li>
                    <li className={`flex justify-between ${c.N === 0 ? 'text-muted-foreground' : ''}`}><span>비유의</span><span className="tabular-nums">{c.N}</span></li>
                    <li className={`flex justify-between ${c.unevaluated === 0 ? 'text-muted-foreground' : ''}`}><span>미평가</span><span className="tabular-nums">{c.unevaluated}</span></li>
                  </ul>
                </div>
              )
            })}
          </div>
        )}
      </CardContent>
    </Card>
  )
}
