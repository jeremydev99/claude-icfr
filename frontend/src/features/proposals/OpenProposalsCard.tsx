import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { ArrowRight, FileCheck2 } from 'lucide-react'
import apiClient from '@/lib/axios'
import { useActiveTenantId } from '@/features/auth/store'
import type { Proposal } from './proposals.pure'

/** 결재가 끝나지 않은 제안 묶음 — 재무제표 화면 위쪽. 없으면 그리지 않는다. */
export default function OpenProposalsCard({ kind }: { kind?: string }) {
  const tenantId = useActiveTenantId()
  const { data = [] } = useQuery({
    queryKey: ['proposals', tenantId, kind],
    queryFn: async () => (await apiClient.get<Proposal[]>('/api/proposals', { params: kind ? { kind } : {} })).data,
    staleTime: 30_000,
  })
  const open = data.filter((p) => p.status === 'pending_review' || p.status === 'reviewed')
  if (open.length === 0) return null
  return (
    <section className="space-y-2 rounded-xl border border-primary/30 bg-accent/60 p-4 shadow-card">
      <h2 className="flex items-center gap-2 text-base font-semibold"><FileCheck2 className="h-5 w-5" />결재 중인 연결 제안</h2>
      {open.map((p) => (
        <Link key={p.id} to={`/proposals/${p.id}`}
          className="flex items-center justify-between rounded-lg border bg-card px-4 py-3 text-sm hover:border-primary/40">
          <span><b>{p.title}</b> · {p.status_label} · 항목 {p.counts.total}</span>
          <ArrowRight className="h-4 w-4" />
        </Link>
      ))}
    </section>
  )
}
