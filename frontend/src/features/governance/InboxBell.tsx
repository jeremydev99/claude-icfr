import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { Link, useLocation } from 'react-router-dom'
import { ArrowRight, Bell } from 'lucide-react'
import { cn } from '@/lib/utils'
import { useInbox } from './useInbox'

/**
 * 상단 알림 배지(13.9-114) — 결재·할 일이 있으면 숫자를 띄우고, 누르면 목록에서 바로 해당 화면으로 간다.
 * 상단 바가 넘침을 자르므로(overflow-hidden) 목록은 body 에 띄운다.
 */
export default function InboxBell() {
  const { data = [] } = useInbox()
  const [open, setOpen] = useState(false)
  const btnRef = useRef<HTMLButtonElement | null>(null)
  const boxRef = useRef<HTMLDivElement | null>(null)
  const [pos, setPos] = useState<{ top: number; right: number }>({ top: 56, right: 12 })
  const { pathname, search } = useLocation()

  useEffect(() => setOpen(false), [pathname, search])
  useEffect(() => {
    if (!open) return
    const r = btnRef.current?.getBoundingClientRect()
    if (r) setPos({ top: r.bottom + 6, right: Math.max(8, window.innerWidth - r.right) })
    const onDown = (e: MouseEvent) => {
      const t = e.target as Node
      if (!boxRef.current?.contains(t) && !btnRef.current?.contains(t)) setOpen(false)
    }
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') setOpen(false) }
    document.addEventListener('mousedown', onDown)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onDown)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  const count = data.length
  const label = count > 0 ? `알림 — 처리할 결재·할 일 ${count}건` : '알림 — 처리할 일이 없습니다'
  return (
    <>
      <button
        ref={btnRef}
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-label={label}
        title={label}
        aria-expanded={open}
        className={cn(
          'relative rounded-lg p-2 text-muted-foreground transition-colors hover:bg-card hover:text-foreground hover:shadow-card',
          open && 'bg-card text-foreground shadow-card',
        )}
      >
        <Bell className="h-5 w-5 md:h-4 md:w-4" />
        {count > 0 && (
          <span className="absolute -right-0.5 -top-0.5 flex h-[18px] min-w-[18px] items-center justify-center rounded-full bg-destructive px-1 text-[11px] font-semibold leading-none text-destructive-foreground">
            {count > 99 ? '99+' : count}
          </span>
        )}
      </button>
      {open && createPortal(
        <div
          ref={boxRef}
          role="dialog"
          aria-label="처리할 결재·할 일"
          style={{ top: pos.top, right: pos.right }}
          className="fixed z-50 w-[min(380px,calc(100vw-16px))] overflow-hidden rounded-xl border bg-popover text-popover-foreground shadow-lg"
        >
          <div className="border-b px-4 py-2.5 text-sm font-semibold">처리할 결재·할 일 {count > 0 && <span className="text-muted-foreground">{count}건</span>}</div>
          {count === 0 ? (
            <p className="px-4 py-6 text-center text-sm text-muted-foreground">지금 처리할 결재나 할 일이 없습니다.</p>
          ) : (
            <ul className="max-h-[60vh] overflow-y-auto py-1">
              {data.map((i) => (
                <li key={`${i.entity_type}-${i.entity_id}-${i.action}`}>
                  <Link to={i.path} className="flex items-center justify-between gap-3 px-4 py-2.5 text-sm hover:bg-muted">
                    <span className="min-w-0">
                      <span className="block truncate font-medium">{i.title}</span>
                      <span className="block text-xs text-muted-foreground">{i.label}</span>
                    </span>
                    <ArrowRight className="h-4 w-4 shrink-0 text-muted-foreground" />
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </div>,
        document.body,
      )}
    </>
  )
}
