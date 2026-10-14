import { useQuery } from '@tanstack/react-query'
import { Loader2 } from 'lucide-react'
import apiClient from '@/lib/axios'
import { useActiveTenantId } from '@/features/auth/store'
import RcmDiffView, { type RcmDiff } from './RcmDiffView'

interface CompareResult extends RcmDiff { base: string; target: string; summary_text: string }

/**
 * 그 자리에서 보는 변경 내용(2026-10-14) — 결재할 때 화면 위쪽 비교 영역까지 가지 않고, 승인 버튼 바로 위에서
 * 통제별 전 → 후를 본다. `base`/`target` 은 `<연도 id>:<버전>` 또는 `live`(현재 RCM).
 */
export default function InlineDiff({ base, target }: { base: string; target: string }) {
  const tenantId = useActiveTenantId()
  const { data, isLoading, error } = useQuery({
    queryKey: ['rcm-compare', tenantId, base, target],
    queryFn: async () => (await apiClient.get<CompareResult>('/api/rcm-years/compare', { params: { base, target } })).data,
  })
  if (isLoading) return <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
  if (error || !data) return <p className="text-sm text-destructive">변경 내용을 불러오지 못했습니다.</p>
  return (
    <div className="space-y-2 rounded-lg border bg-background p-3">
      <p className="text-sm"><b>{data.base}</b> → <b>{data.target}</b>: {data.summary_text}</p>
      <RcmDiffView diff={data} />
    </div>
  )
}
