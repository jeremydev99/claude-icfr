import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import apiClient from '@/lib/axios'
import { useActiveTenantId } from '@/features/auth/store'
import { effectiveStatus } from '../moduleStatus.pure'
import { navigation, type ModuleStatus, type NavItem } from '@/config/navigation'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'
import HelpButton from '@/features/help/HelpButton'

/**
 * 배지 문구 — 상태의 **차이**가 드러나는 말을 쓴다.
 *
 * "사용 가능"은 쓰지 않았다. RCM 도 사용 가능하므로 구분이 되지 않는다.
 * 실제로 다른 것은 **데이터가 있느냐**이고, 그것이 "다음에 뭘 해야 하는지"를 가리킨다.
 * "데이터 없음"만 보면 고장으로 읽힐 수 있어 카드 목록 위에 한 줄 범례를 둔다.
 */
const STATUS_META: Record<ModuleStatus, { label: string; variant: 'default' | 'secondary' | 'outline' }> = {
  live: { label: '실데이터', variant: 'default' },
  ready: { label: '데이터 없음', variant: 'secondary' },
  draft: { label: '초안', variant: 'outline' },
  api: { label: 'API 있음', variant: 'secondary' },
  todo: { label: '준비중', variant: 'outline' },
}

/** 배지만으로는 "데이터 없음"이 고장으로 읽힐 수 있어 범례로 뜻을 적는다. */
const STATUS_LEGEND: Record<ModuleStatus, string> = {
  live: '데이터가 쌓여 있음',
  ready: '화면은 동작하며 입력하면 바로 쌓임',
  draft: '초안 화면 — 운영에 맞춰 조정 예정',
  api: 'API 는 있고 화면이 아직 없음',
  todo: '화면 미구현',
}

function ModuleCard({ item, count }: { item: NavItem; count?: number }) {
  const navigate = useNavigate()
  const status = effectiveStatus(item.status ?? 'todo', count)
  const meta = STATUS_META[status]
  const Icon = item.icon

  return (
    <button
      type="button"
      onClick={() => navigate(item.path)}
      className={cn(
        'flex h-full flex-col gap-2 rounded-lg border p-4 text-left transition-colors hover:bg-accent',
        status === 'todo' && 'bg-muted/40 text-muted-foreground',
      )}
    >
      <div className="flex items-center justify-between gap-2">
        <span className="flex items-center gap-2 font-medium">
          <Icon className="h-4 w-4 shrink-0" />
          {item.label}
        </span>
        <span className="flex items-center gap-1.5">
          {count ? <span className="text-xs tabular-nums text-muted-foreground">{count.toLocaleString('ko-KR')}건</span> : null}
          <Badge variant={meta.variant}>{meta.label}</Badge>
        </span>
      </div>
      <p className="line-clamp-2 text-xs text-muted-foreground">{item.description}</p>
    </button>
  )
}

export default function ModuleCards() {
  // 사이드바 정의를 그대로 쓴다 — 메뉴와 카드가 어긋나지 않게 목록을 두 곳에 두지 않는다.
  // 대시보드 자기 자신은 뺀다(`status` 없는 항목).
  const items = navigation.flatMap((g) => g.items).filter((i) => i.status)
  // 메뉴별 실제 데이터 건수(GET /api/dashboard/modules) — 실패하면 고정 상태만 쓴다
  const tenantId = useActiveTenantId()
  const { data: counts } = useQuery({
    queryKey: ['tenant', tenantId ?? 'no-tenant', 'dashboard', 'modules'],
    queryFn: async () => (await apiClient.get<Record<string, number>>('/api/dashboard/modules')).data,
    staleTime: 60_000,
  })

  return (
    <section className="space-y-3">
      {/* 제목과 범례를 한 줄에 두면 좁은 폭에서 범례 끝이 잘린다 — 줄을 나누고 범례 안에서도
          항목 단위로 감싸지게 한다(A-2). */}
      <div className="space-y-1">
        <h2 className="flex items-center gap-1 text-lg font-semibold">
          모듈 현황
          <HelpButton k="screen.dashboard.module-status" />
        </h2>
        <ul className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
          {(Object.keys(STATUS_META) as ModuleStatus[]).map((key) => (
            <li key={key} className="whitespace-nowrap">
              <strong className="font-semibold">{STATUS_META[key].label}</strong>{' '}
              {STATUS_LEGEND[key]}
            </li>
          ))}
        </ul>
      </div>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
        {items.map((item) => (
          <ModuleCard key={item.path} item={item} count={counts?.[item.path]} />
        ))}
      </div>
    </section>
  )
}
