import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'
import Illustration from './Illustration'
import type { IllustrationSlot } from './manifest'

/**
 * 빈 상태 — 일러스트 + 제목 + 안내 + (선택) 다음 행동 버튼.
 * "데이터 없음" 한 줄 대신 **무엇을 하면 채워지는지**를 보여 주는 것이 목적이다.
 */
export default function EmptyState({
  slot = 'empty-default',
  title,
  description,
  action,
  className,
  compact,
}: {
  slot?: IllustrationSlot
  title: string
  description?: ReactNode
  action?: ReactNode
  className?: string
  compact?: boolean
}) {
  return (
    <div className={cn('flex flex-col items-center justify-center rounded-xl border border-dashed bg-card/60 text-center',
      compact ? 'gap-2 px-4 py-6' : 'gap-3 px-6 py-10', className)}>
      <Illustration slot={slot} className={compact ? 'h-20 w-20' : 'h-32 w-32'} />
      <p className="text-[15px] font-semibold text-foreground">{title}</p>
      {description && <div className="max-w-md text-sm text-muted-foreground">{description}</div>}
      {action && <div className="mt-1">{action}</div>}
    </div>
  )
}
