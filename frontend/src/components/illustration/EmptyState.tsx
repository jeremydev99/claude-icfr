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
      {/* 생성 배경이 완전한 흰색이 아니라 가장자리를 원형으로 사라지게 한다 — 카드 위에 사각 경계가 남지 않게 */}
      <Illustration slot={slot} className={cn(compact ? 'h-24 w-24' : 'h-36 w-36', '[mask-image:radial-gradient(circle,black_48%,transparent_70%)]')} />
      <p className="text-[15px] font-semibold text-foreground">{title}</p>
      {description && <div className="max-w-md text-sm text-muted-foreground">{description}</div>}
      {action && <div className="mt-1">{action}</div>}
    </div>
  )
}
