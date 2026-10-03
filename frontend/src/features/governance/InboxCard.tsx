import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { ArrowRight, Inbox } from 'lucide-react'
import apiClient from '@/lib/axios'
import { useActiveTenantId } from '@/features/auth/store'
import type { InboxItem } from './types'

/** 대시보드 "내 결재 대기" — 지금 내가 처리할 검토·승인·재오픈 결정. 없으면 카드를 그리지 않는다. */
export default function InboxCard() {
  const tenantId = useActiveTenantId()
  const { data = [] } = useQuery({
    queryKey: ['governance-inbox', tenantId],
    queryFn: async () => (await apiClient.get<InboxItem[]>('/api/governance/inbox')).data,
    staleTime: 30_000,
  })
  if (data.length === 0) return null
  return (
    <section className="rounded-xl border border-primary/30 bg-accent/60 p-5 shadow-card">
      <h2 className="flex items-center gap-2 text-base font-semibold">
        <Inbox className="h-5 w-5" /> 내 결재 대기 <span className="rounded-full bg-primary px-2 text-sm text-primary-foreground">{data.length}</span>
      </h2>
      <ul className="mt-3 space-y-2">
        {data.map((i) => (
          <li key={`${i.entity_id}-${i.action}`}>
            <Link to={i.path} className="flex items-center justify-between rounded-lg border bg-card px-4 py-3 text-sm transition-colors hover:border-primary/40">
              <span><b>{i.title}</b> · {i.label}</span>
              <ArrowRight className="h-4 w-4" />
            </Link>
          </li>
        ))}
      </ul>
    </section>
  )
}
