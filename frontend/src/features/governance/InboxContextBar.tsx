import { Link, useLocation } from 'react-router-dom'
import { ArrowRight, Stamp } from 'lucide-react'
import { useInbox } from './useInbox'
import { contextItems } from './governance.pure'

/**
 * 이 화면에서 처리할 결재 진입로(13.9-114) — 결재가 같은 메뉴의 다른 탭(예: RCM 통제 탭에서 '회계연도 확정' 탭의
 * 재오픈 승인)에 있어도 지금 보는 화면 맨 위에서 바로 그 자리로 간다. 다른 메뉴의 결재는 상단 알림 배지에서.
 */
export default function InboxContextBar() {
  const { data = [] } = useInbox()
  const { pathname, search } = useLocation()
  const items = contextItems(data, pathname, search)
  if (items.length === 0) return null
  return (
    <div className="border-b border-primary/20 bg-accent/60 px-4 py-2 text-sm md:px-8">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
        <span className="flex items-center gap-1.5 font-medium"><Stamp className="h-4 w-4" />이 화면에서 처리할 결재</span>
        {items.map((i) => (
          <Link key={`${i.entity_type}-${i.entity_id}-${i.action}`} to={i.path}
            className="inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-primary hover:bg-card hover:underline">
            {i.title} · {i.label}<ArrowRight className="h-3.5 w-3.5" />
          </Link>
        ))}
      </div>
    </div>
  )
}
