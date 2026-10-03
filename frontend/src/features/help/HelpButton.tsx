import { HelpCircle } from 'lucide-react'
import { cn } from '@/lib/utils'
import { useHelpPanel } from './store'

/** 섹션 제목 옆 "?" — `<HelpButton k="screen.scoping.materiality" />`. 패널을 그 항목으로 연다. */
export default function HelpButton({ k, className, label = '이 영역 설명 보기' }: { k: string; className?: string; label?: string }) {
  const openAt = useHelpPanel((s) => s.openAt)
  return (
    <button
      type="button"
      onClick={(e) => {
        e.stopPropagation()
        openAt(k)
      }}
      className={cn(
        'inline-flex h-5 w-5 flex-shrink-0 items-center justify-center rounded-full align-middle text-muted-foreground hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring',
        className,
      )}
      aria-label={label}
      title={label}
    >
      <HelpCircle className="h-3.5 w-3.5" />
    </button>
  )
}
