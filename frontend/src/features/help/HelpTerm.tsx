import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'
import { useHelpPanel } from './store'

/**
 * 화면 속 용어 표식 — `<HelpTerm k="term.assertion">어서션</HelpTerm>`.
 * **점선 밑줄을 보이게 둔다**(13.9-8) — 표식이 없으면 아무도 기능을 발견하지 못한다.
 * 문구는 바꾸지 않고 감싸기만 한다.
 */
export default function HelpTerm({ k, children, className }: { k: string; children: ReactNode; className?: string }) {
  const openAt = useHelpPanel((s) => s.openAt)
  return (
    <button
      type="button"
      onClick={(e) => {
        e.stopPropagation()
        openAt(k)
      }}
      className={cn(
        'inline cursor-help p-0 underline decoration-dotted decoration-muted-foreground/70 underline-offset-4 hover:decoration-primary focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring rounded-sm',
        className,
      )}
      title="용어 설명 보기"
    >
      {children}
    </button>
  )
}
