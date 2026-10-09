import { useEffect, useRef, useState, useSyncExternalStore } from 'react'
import type { PointerEvent as ReactPointerEvent } from 'react'
import { useLocation } from 'react-router-dom'
import { ChevronDown, ChevronRight, X } from 'lucide-react'
import { Sheet, SheetContent, SheetTitle } from '@/components/ui/sheet'
import { cn } from '@/lib/utils'
import { useHelpByKey, useHelpByPrefix } from './api'
import {
  EMPTY_HELP_MESSAGE,
  HELP_PUSH_MIN_VIEWPORT,
  TERM_PREFIX,
  formatSource,
  hasBody,
  menuKeyForRoute,
  screenPrefixForRoute,
} from './help.pure'
import { useHelpPanel } from './store'
import type { HelpText } from './types'

const PUSH_QUERY = `(min-width: ${HELP_PUSH_MIN_VIEWPORT}px)`

/** 넓은 화면(≥1280px)인지. 이 폭 이상이면 패널이 본문을 밀고, 미만이면 겹친다(help.pure 참조). */
function useIsWide(): boolean {
  return useSyncExternalStore(
    (cb) => {
      const mq = window.matchMedia(PUSH_QUERY)
      mq.addEventListener('change', cb)
      return () => mq.removeEventListener('change', cb)
    },
    () => window.matchMedia(PUSH_QUERY).matches,
    () => true,
  )
}

/** 항목 하나. 본문 줄바꿈 유지, 미작성이면 중립 문구(지어내지 않는다). */
function HelpEntry({
  item,
  focused,
  heading = 'h3',
  entryRef,
}: {
  item: HelpText
  focused: boolean
  heading?: 'h2' | 'h3'
  entryRef?: (el: HTMLElement | null) => void
}) {
  const H = heading
  const source = formatSource(item.source, item.as_of)
  return (
    <section
      ref={entryRef}
      className={cn(
        'scroll-mt-2 rounded-md border border-transparent px-3 py-2.5 transition-colors',
        focused && 'border-primary/40 bg-primary/5',
      )}
    >
      <H className={cn('font-semibold', heading === 'h2' ? 'text-base' : 'text-sm')}>
        {item.title ?? <span className="font-mono text-xs font-normal text-muted-foreground">{item.key}</span>}
      </H>
      {hasBody(item.body) ? (
        <p className="mt-1 whitespace-pre-line break-words text-sm leading-relaxed text-foreground/90">{item.body}</p>
      ) : (
        <p className="mt-1 text-sm text-muted-foreground">{EMPTY_HELP_MESSAGE}</p>
      )}
      {source && <p className="mt-1.5 text-xs text-muted-foreground">{source}</p>}
    </section>
  )
}

/** 키 자체가 없을 때(404). 문구를 지어내지 않고 중립 상태만 보인다. */
function EmptyEntry({ k }: { k: string }) {
  return (
    <section className="rounded-md border border-primary/40 bg-primary/5 px-3 py-2.5">
      <p className="font-mono text-xs text-muted-foreground">{k}</p>
      <p className="mt-1 text-sm text-muted-foreground">{EMPTY_HELP_MESSAGE}</p>
    </section>
  )
}

/** 패널 내용 — 밀기(aside)·겹치기(Sheet) 두 모드가 같은 것을 쓴다. */
function HelpPanelContent({ showClose }: { showClose: boolean }) {
  const { pathname } = useLocation()
  const focusKey = useHelpPanel((s) => s.focusKey)
  const focusSeq = useHelpPanel((s) => s.focusSeq)
  const close = useHelpPanel((s) => s.close)
  const menuKey = menuKeyForRoute(pathname)
  const screenPrefix = screenPrefixForRoute(pathname)

  const menuQ = useHelpByPrefix(menuKey)
  const screenQ = useHelpByPrefix(screenPrefix)
  const termQ = useHelpByPrefix(TERM_PREFIX)

  // menu.<route> 접두사 조회는 하위 키도 돌려줄 수 있으므로 정확히 같은 키만 머리글로 쓴다.
  const menuEntry = menuQ.data?.find((h) => h.key === menuKey) ?? null
  // 하위 화면(예: /rcm 의 /rcm/links)은 자기 menu.* 를 가진다 — 그 화면의 screen.* 는 상위 화면 패널에서 뺀다.
  const subScreenPrefixes = (menuQ.data ?? [])
    .filter((h) => h.key !== menuKey)
    .map((h) => `screen.${h.key.slice('menu.'.length)}.`)
  const screenEntries = (screenQ.data ?? []).filter((h) => !subScreenPrefixes.some((p) => h.key.startsWith(p)))
  const terms = termQ.data ?? []

  const onScreen =
    focusKey !== null && ((menuEntry !== null && focusKey === menuKey) || screenEntries.some((h) => h.key === focusKey))
  const listsLoaded = !menuQ.isLoading && !screenQ.isLoading && !termQ.isLoading
  // 화면 밖 키(용어 등)는 맨 위에 고정해 보인다. 용어 목록에 있으면 그것을 쓰고, 없으면 단건 조회.
  const pinnedFromTerms = focusKey && !onScreen ? (terms.find((h) => h.key === focusKey) ?? null) : null
  const needSingle = focusKey !== null && !onScreen && listsLoaded && pinnedFromTerms === null
  const singleQ = useHelpByKey(needSingle ? focusKey : null)
  const pinned = pinnedFromTerms ?? singleQ.data ?? null

  const [termsOpen, setTermsOpen] = useState(false)
  const scrollBoxRef = useRef<HTMLDivElement | null>(null)
  const entryEls = useRef(new Map<string, HTMLElement>())
  const refFor = (key: string) => (el: HTMLElement | null) => {
    if (el) entryEls.current.set(key, el)
    else entryEls.current.delete(key)
  }

  // focusKey(또는 같은 키 재클릭 = focusSeq)가 바뀌면 그 항목으로 스크롤한다. 고정 항목은 맨 위.
  useEffect(() => {
    if (!focusKey) return
    if (!onScreen) {
      scrollBoxRef.current?.scrollTo({ top: 0, behavior: 'smooth' })
      return
    }
    entryEls.current.get(focusKey)?.scrollIntoView({ block: 'start', behavior: 'smooth' })
  }, [focusKey, focusSeq, onScreen, screenEntries.length])

  const loading = menuQ.isLoading || screenQ.isLoading
  const error = menuQ.isError || screenQ.isError || termQ.isError

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex h-12 flex-shrink-0 items-center justify-between border-b px-4">
        <p className="text-sm font-semibold">도움말</p>
        {showClose && (
          <button
            type="button"
            onClick={close}
            className="rounded-md p-1.5 text-muted-foreground hover:bg-muted hover:text-foreground"
            aria-label="도움말 닫기 (Esc)"
            title="닫기 (Esc)"
          >
            <X className="h-4 w-4" />
          </button>
        )}
      </div>

      <div ref={scrollBoxRef} className="min-h-0 flex-1 space-y-3 overflow-y-auto px-2 py-3">
        {focusKey && !onScreen && (pinned !== null || (needSingle && !singleQ.isLoading)) && (
          <div className="space-y-1">
            <p className="px-3 text-[11px] font-medium tracking-wider text-muted-foreground">선택한 항목</p>
            {pinned ? <HelpEntry item={pinned} focused /> : <EmptyEntry k={focusKey} />}
          </div>
        )}

        {error && <p className="px-3 text-sm text-destructive">도움말을 불러오지 못했습니다.</p>}
        {loading && <p className="px-3 text-sm text-muted-foreground">불러오는 중…</p>}

        {!loading && !error && (
          <>
            {menuEntry ? (
              <HelpEntry
                item={menuEntry}
                heading="h2"
                focused={focusKey === menuEntry.key}
                entryRef={refFor(menuEntry.key)}
              />
            ) : (
              <p className="px-3 text-sm text-muted-foreground">{EMPTY_HELP_MESSAGE}</p>
            )}
            {screenEntries.length > 0 && (
              <div className="space-y-1 border-t pt-2">
                {screenEntries.map((h) => (
                  <HelpEntry key={h.key} item={h} focused={focusKey === h.key} entryRef={refFor(h.key)} />
                ))}
              </div>
            )}
          </>
        )}

        {terms.length > 0 && (
          <div className="border-t pt-2">
            <button
              type="button"
              onClick={() => setTermsOpen((v) => !v)}
              className="flex w-full items-center gap-1 rounded-md px-3 py-1.5 text-sm font-semibold hover:bg-muted"
              aria-expanded={termsOpen}
            >
              {termsOpen ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
              용어
              <span className="ml-1 text-xs font-normal text-muted-foreground">{terms.length}</span>
            </button>
            {termsOpen && (
              <div className="mt-1 space-y-1">
                {terms.map((h) => (
                  <HelpEntry key={h.key} item={h} focused={focusKey === h.key} />
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

/** 패널 왼쪽 가장자리 드래그로 폭 조절. 키보드(←/→)로도 조절된다. */
function ResizeHandle() {
  const width = useHelpPanel((s) => s.width)
  const setWidth = useHelpPanel((s) => s.setWidth)
  const onPointerDown = (e: ReactPointerEvent<HTMLDivElement>) => {
    e.preventDefault()
    const startX = e.clientX
    const startW = width
    // 패널은 오른쪽에 있으므로 왼쪽으로 끌수록(clientX 감소) 넓어진다.
    const onMove = (ev: PointerEvent) => setWidth(startW + (startX - ev.clientX))
    const onUp = () => {
      window.removeEventListener('pointermove', onMove)
      window.removeEventListener('pointerup', onUp)
      document.body.style.removeProperty('cursor')
      document.body.style.removeProperty('user-select')
    }
    document.body.style.cursor = 'col-resize'
    document.body.style.userSelect = 'none'
    window.addEventListener('pointermove', onMove)
    window.addEventListener('pointerup', onUp)
  }
  return (
    <div
      role="separator"
      aria-orientation="vertical"
      aria-label="도움말 패널 폭 조절"
      aria-valuenow={width}
      tabIndex={0}
      onPointerDown={onPointerDown}
      onKeyDown={(e) => {
        if (e.key === 'ArrowLeft') setWidth(width + 16)
        else if (e.key === 'ArrowRight') setWidth(width - 16)
      }}
      className="absolute inset-y-0 -left-1 z-10 w-2 cursor-col-resize touch-none hover:bg-primary/20 focus-visible:bg-primary/30 focus-visible:outline-none"
    />
  )
}

/**
 * 매뉴얼 패널 (7-B, 13.9-8).
 * - 넓은 화면(≥ HELP_PUSH_MIN_VIEWPORT = 1280px): 오른쪽 aside 로 **본문을 민다**(겹치지 않음) —
 *   입력하면서 읽을 수 있게. 폭은 왼쪽 가장자리 드래그로 조절, localStorage 에 저장(280~640px, 기본 360).
 * - 좁은 화면(<1280px): 본문 위에 **겹치는** Sheet. 폭은 min(90vw, 400px) — 가로 스크롤을 만들지 않는다.
 * AppLayout 가로 flex 행의 마지막 자식으로 둔다.
 */
export default function HelpPanel() {
  const open = useHelpPanel((s) => s.open)
  const width = useHelpPanel((s) => s.width)
  const close = useHelpPanel((s) => s.close)
  const wide = useIsWide()

  // 밀기 모드의 Esc 닫기. 겹치기(Sheet)는 Radix 가 Esc 를 처리한다.
  // 다른 다이얼로그가 열려 있으면 그쪽 Esc 이므로 건드리지 않는다.
  useEffect(() => {
    if (!open || !wide) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== 'Escape' || e.defaultPrevented) return
      if (document.querySelector('[role="dialog"][data-state="open"], [role="alertdialog"][data-state="open"]')) return
      close()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, wide, close])

  if (wide) {
    if (!open) return null
    return (
      <aside
        className="sticky top-0 h-screen flex-shrink-0 border-l bg-background"
        style={{ width, maxWidth: '45vw' }}
        aria-label="도움말"
      >
        <ResizeHandle />
        <HelpPanelContent showClose />
      </aside>
    )
  }

  return (
    <Sheet open={open} onOpenChange={(v) => !v && close()}>
      <SheetContent side="right" className="w-[90vw] max-w-[400px] p-0 sm:max-w-[400px]">
        <SheetTitle className="sr-only">도움말</SheetTitle>
        <HelpPanelContent showClose={false} />
      </SheetContent>
    </Sheet>
  )
}
