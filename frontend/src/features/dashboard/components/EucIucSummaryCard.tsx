import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { cn } from '@/lib/utils'
import { useEucSummary } from '@/features/euc/api/useEucIuc'
import type { CountBucket } from '@/features/euc/types'

/**
 * 대시보드 EUC·IUC 카드 (5-1).
 *
 * **0 건도 0 으로, 미평가는 따로** 보인다. 원천 8건이 전부 Low 로 적혀 있어도 우리 모델은
 * 복잡도 없이 등급을 내지 않으므로 "식별 대상 0건"만 보이면 평가해서 낮은 것처럼 읽힌다 —
 * 그래서 미평가 칸과 원천 참고값 불일치 수를 함께 둔다.
 *
 * 제목 색은 RCM 카드와 같은 묶음 규칙이다 — 속성(파랑)·현황(호박).
 */
function Block({ title, tone, children }: { title: string; tone: 'attribute' | 'status'; children: ReactNode }) {
  return (
    <div className="rounded-md border p-3">
      <h3
        className={cn(
          '-m-3 mb-2 rounded-t-md border-b px-3 py-2 text-sm font-semibold',
          tone === 'attribute' ? 'border-blue-100 bg-blue-50 text-blue-900' : 'border-amber-100 bg-amber-50 text-amber-900',
        )}
      >
        {title}
      </h3>
      {children}
    </div>
  )
}

function Rows({ buckets }: { buckets: CountBucket[] }) {
  return (
    <ul className="space-y-1 text-sm">
      {buckets.map((b) => (
        <li
          key={b.value}
          className={cn('flex items-center justify-between border-b pb-1 last:border-b-0', b.count === 0 && 'text-muted-foreground')}
        >
          <span>{b.label}</span>
          <span className="tabular-nums font-medium">{b.count}</span>
        </li>
      ))}
    </ul>
  )
}

export default function EucIucSummaryCard() {
  const { data, isLoading, isError } = useEucSummary()

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex flex-wrap items-baseline gap-3">
          <span>
            <Link to="/euc" className="hover:underline">EUC</Link>
            {' · '}
            <Link to="/iuc" className="hover:underline">IUC</Link>
          </span>
          {data && (
            <span className="text-sm font-normal text-muted-foreground">
              EUC 파일 {data.file_total}건 · 정보 항목 {data.item_total}건
            </span>
          )}
        </CardTitle>
      </CardHeader>
      <CardContent>
        {isLoading && <p className="text-sm text-muted-foreground">집계를 불러오는 중…</p>}
        {isError && <p className="text-sm text-destructive">집계를 불러오지 못했습니다</p>}
        {data && (
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
            <Block title="통제 식별" tone="status">
              <ul className="space-y-1 text-sm">
                <li className="flex items-center justify-between border-b pb-1">
                  <span>식별 대상</span>
                  <span className="tabular-nums font-medium">{data.identified}</span>
                </li>
                <li className="flex items-center justify-between border-b pb-1">
                  <span className="text-muted-foreground">미평가(판정 불가)</span>
                  <span className="tabular-nums font-medium">{data.unevaluated}</span>
                </li>
                <li className="flex items-center justify-between border-b pb-1">
                  <span className="text-muted-foreground">참조 통제 0건 파일</span>
                  <span className="tabular-nums font-medium">{data.unreferenced_files}</span>
                </li>
                <li className="flex items-center justify-between">
                  <span className="text-muted-foreground">원천 참고값과 다름</span>
                  <span className="tabular-nums font-medium">{data.source_mismatch}</span>
                </li>
              </ul>
              <p className="pt-2 text-xs text-muted-foreground">
                임계값: 위험 등급 {data.identification_threshold} 이상
              </p>
            </Block>
            <Block title="위험 등급 (파일)" tone="attribute">
              <Rows buckets={data.risk_grade} />
            </Block>
            <Block title="중요성 (정보 항목)" tone="attribute">
              <Rows buckets={data.importance} />
            </Block>
            <Block title="정보 Type" tone="attribute">
              <Rows buckets={data.info_type} />
            </Block>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
