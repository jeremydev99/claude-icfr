import { useState } from 'react'
import { Link } from 'react-router-dom'
import { ChevronDown, ChevronRight } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { useRcmSummary } from '../api/useRcmSummary'
import { useDrilldownControls } from '../api/useDrilldownControls'
import type { RcmSummary, SummaryBucket, SummaryGroup } from '../api/types'

/** 드릴스루 링크. RCM 화면이 마운트 시 이 파라미터를 읽어 필터를 걸고 시작한다(단방향). */
function rcmLink(param: string, value: string) {
  return `/rcm?${encodeURIComponent(param)}=${encodeURIComponent(value)}`
}

function BucketRow({ group, bucket }: { group: SummaryGroup; bucket: SummaryBucket }) {
  const [open, setOpen] = useState(false)
  const { data, isLoading, isError } = useDrilldownControls(group.filter_param, bucket.value, open)
  const Chevron = open ? ChevronDown : ChevronRight

  return (
    <li className="border-b last:border-b-0">
      <div className="flex items-center gap-2 py-1.5">
        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          className="flex flex-1 items-center gap-1 text-left text-sm hover:underline"
          aria-expanded={open}
        >
          <Chevron className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
          <span className="flex-1">{bucket.label}</span>
          <span className="tabular-nums font-medium">{bucket.count}</span>
        </button>
        {group.filter_param && (
          <Link
            to={rcmLink(group.filter_param, bucket.value)}
            className="shrink-0 text-xs text-muted-foreground hover:text-foreground hover:underline"
          >
            RCM에서 보기
          </Link>
        )}
      </div>

      {open && (
        <div className="pb-2 pl-5">
          {isLoading && <p className="text-xs text-muted-foreground">불러오는 중…</p>}
          {isError && <p className="text-xs text-destructive">목록을 불러오지 못했습니다</p>}
          {data && data.items.length === 0 && (
            <p className="text-xs text-muted-foreground">해당 통제가 없습니다</p>
          )}
          {data && data.items.length > 0 && (
            <ul className="max-h-64 space-y-0.5 overflow-y-auto">
              {data.items.map((c) => (
                <li key={c.id}>
                  {/* 개별 통제로 이동 — 코드 검색어를 걸어 그 통제가 목록에 보이는 상태로 진입한다 */}
                  <Link
                    to={rcmLink('q', c.code)}
                    className="block truncate py-0.5 text-xs text-muted-foreground hover:text-foreground hover:underline"
                    title={`${c.code} ${c.name}`}
                  >
                    <span className="font-mono">{c.code}</span> {c.name}
                  </Link>
                </li>
              ))}
            </ul>
          )}
          {data && data.total > data.items.length && (
            <p className="pt-1 text-xs text-muted-foreground">
              {data.items.length}건 표시 / 전체 {data.total}건 —{' '}
              {group.filter_param && (
                <Link to={rcmLink(group.filter_param, bucket.value)} className="underline">
                  RCM에서 전체 보기
                </Link>
              )}
            </p>
          )}
        </div>
      )}
    </li>
  )
}

function GroupBlock({ group }: { group: SummaryGroup }) {
  return (
    <div className="rounded-md border p-3">
      <h3 className="mb-1 text-sm font-semibold">{group.label}</h3>
      {group.key === 'activity' && (
        // 한 통제가 여러 활동을 가지므로 합이 전체와 다르다. 안 적으면 "숫자가 틀렸다"로 읽힌다.
        <p className="mb-1 text-xs text-muted-foreground">한 통제가 여러 유형에 해당할 수 있습니다</p>
      )}
      <ul>
        {group.buckets.length === 0 && (
          <li className="py-1.5 text-sm text-muted-foreground">0건</li>
        )}
        {group.buckets.map((b) => (
          <BucketRow key={`${group.key}-${b.value}`} group={group} bucket={b} />
        ))}
      </ul>
    </div>
  )
}

function OrgBlock({ summary }: { summary: RcmSummary }) {
  const { org } = summary
  return (
    <div className="rounded-md border p-3">
      <h3 className="mb-1 text-sm font-semibold">통제 조직별</h3>
      <p className="mb-1 text-xs text-muted-foreground">
        통제책임자 배정 → 그 사람의 주 소속 부서 기준
      </p>
      <ul className="space-y-1 text-sm">
        {org.buckets.map((b) => (
          <li key={b.value} className="flex items-center justify-between border-b pb-1">
            <span>{b.label}</span>
            <span className="tabular-nums font-medium">{b.count}</span>
          </li>
        ))}
        {/* 0 을 가리지 않는다 — 미배정이 전체인 상태가 지금의 현황이다 */}
        <li className="flex items-center justify-between pt-0.5">
          <span className="text-muted-foreground">미배정</span>
          <span className="tabular-nums font-medium">{org.unassigned}</span>
        </li>
      </ul>
    </div>
  )
}

function ProgressBlock({ summary }: { summary: RcmSummary }) {
  const { progress } = summary
  const rows: Array<[string, number]> = [
    ['평가 회차', progress.cycles],
    ['진행 의무(회차×통제)', progress.targets],
    ['통제활동', progress.activities],
    ['완료', progress.completed],
    ['미완료', progress.incomplete],
  ]
  return (
    <div className="rounded-md border p-3">
      <h3 className="mb-1 text-sm font-semibold">진행 현황</h3>
      <p className="mb-1 text-xs text-muted-foreground">
        평가 회차가 생성되면 자동으로 채워집니다
      </p>
      <ul className="space-y-1 text-sm">
        {rows.map(([label, value]) => (
          <li key={label} className="flex items-center justify-between border-b pb-1 last:border-b-0">
            <span>{label}</span>
            <span className="tabular-nums font-medium">{value}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}

export default function RcmSummaryCard() {
  const { data, isLoading, isError } = useRcmSummary()

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-baseline gap-3">
          <Link to="/rcm" className="hover:underline">
            RCM 관리
          </Link>
          {data && (
            <span className="text-sm font-normal text-muted-foreground">
              통제 {data.control_total}건 · 프로세스 {data.process_total}개
            </span>
          )}
        </CardTitle>
      </CardHeader>
      <CardContent>
        {isLoading && <p className="text-sm text-muted-foreground">집계를 불러오는 중…</p>}
        {isError && <p className="text-sm text-destructive">집계를 불러오지 못했습니다</p>}
        {data && (
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {data.groups.map((g) => (
              <GroupBlock key={g.key} group={g} />
            ))}
            <OrgBlock summary={data} />
            <ProgressBlock summary={data} />
          </div>
        )}
      </CardContent>
    </Card>
  )
}
