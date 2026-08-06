// ICFR-PROMPT-envelope-required.md 5단계. 목록·상세 공용 — 필터·정렬 로직 없음, 표시 전용.
import { Badge } from '@/components/ui/badge'
import type { SourceEnvelope } from '../api/sourceEnvelope'

export default function SourceBadge({ envelope }: { envelope: SourceEnvelope }) {
  if (envelope.is_overridden) {
    return (
      <Badge className="border-blue-200 bg-blue-100 text-blue-700 hover:bg-blue-100 text-xs">
        재정의
      </Badge>
    )
  }
  if (envelope.source === 'tenant') {
    return (
      <Badge variant="secondary" className="text-xs">
        테넌트
      </Badge>
    )
  }
  return (
    <Badge variant="outline" className="text-xs text-muted-foreground">
      기준
    </Badge>
  )
}
