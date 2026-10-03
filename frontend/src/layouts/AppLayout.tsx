import { useEffect, useRef, useState } from 'react'
import { Outlet, NavLink, useLocation } from 'react-router-dom'
import { ChevronDown, ChevronRight, ChevronsDownUp, ChevronsUpDown, HelpCircle, KeyRound, Lock, LogOut, Menu, ShieldCheck } from 'lucide-react'
import { useAuthStore } from '@/features/auth/store'
import { isIcfrManagerForUser } from '@/features/auth/permissions.pure'
import { daysLeft, isPathAllowed } from '@/features/auth/externalScope.pure'
import MfaDialog from '@/features/auth/mfa/MfaDialog'
import { useLogout, useMe } from '@/features/auth/hooks/useAuth'
import { SIDEBAR_THEMES, applySidebarTheme, useSidebarTheme } from '@/features/admin/sidebarTheme'
import InstallButton from '@/features/pwa/InstallButton'
import HelpPanel from '@/features/help/HelpPanel'
import { useHelpPanel } from '@/features/help/store'
import ChangePasswordDialog from '@/features/auth/components/ChangePasswordDialog'
import { Sheet, SheetContent, SheetTitle } from '@/components/ui/sheet'
import { cn } from '@/lib/utils'
import LogoMark from '@/components/brand/LogoMark'
import { navigation, type NavItem } from '@/config/navigation'

const NAV_GROUPS_KEY = 'icfr.nav.expandedGroups'

/** 테마 견본 색 — 실제 사이드바 배경과 같은 색 */
const THEME_SWATCH: Record<string, string> = {
  gray: 'bg-[hsl(222_20%_93%)]',
  white: 'bg-white',
  navy: 'bg-[hsl(224_40%_15%)]',
}

/** 시스템 관리 권한(users.role) 표기 */
const ROLE_LABEL: Record<string, string> = { admin: '시스템 관리자', user: '사용자' }

/** 이름 → 아바타 글자. 한글 이름은 성을 뺀 두 글자(용남), 영문은 이니셜 두 개. */
function initials(name: string): string {
  const n = name.trim()
  if (!n) return '?'
  if (/^[가-힣]+$/.test(n)) return n.length >= 3 ? n.slice(1, 3) : n
  return n.split(/\s+/).map((w) => w[0]).join('').slice(0, 2).toUpperCase()
}

/** 현재 경로 → 메뉴 이름(상단 바 제목). 가장 길게 일치하는 메뉴를 고른다(/admin/departments 등). */
function currentTitle(pathname: string): string | null {
  let best: { len: number; label: string } | null = null
  for (const g of navigation) {
    for (const it of g.items) {
      const match = it.path === '/' ? pathname === '/' : pathname === it.path || pathname.startsWith(it.path + '/')
      if (match && (!best || it.path.length > best.len)) best = { len: it.path.length, label: it.label }
    }
  }
  return best?.label ?? null
}

/** 메뉴 한 줄. 권한이 없으면 **숨기지 않고 잠근다** — 숨기면 "그런 기능이 있는지"조차 모른다. */
function NavRow({ item, locked, onNavigate }: { item: NavItem; locked: boolean; onNavigate?: () => void }) {
  if (locked) {
    return (
      <div
        className="flex cursor-not-allowed items-center gap-3 rounded-lg px-3 py-2.5 text-[0.95rem] text-sidebar-muted/60"
        title="내부회계관리자만 사용할 수 있습니다"
      >
        <item.icon className="h-5 w-5 flex-shrink-0" />
        <span className="flex-1">{item.label}</span>
        <Lock className="h-3 w-3 flex-shrink-0" />
      </div>
    )
  }
  return (
    <NavLink
      to={item.path}
      onClick={onNavigate}
      className={({ isActive }) =>
        cn(
          // 선택: 옅은 브랜드 바탕 + 브랜드색 글자 + 왼쪽 막대(before:)
          'relative flex items-center gap-3 rounded-lg px-3 py-2.5 text-[0.95rem] transition-colors duration-150',
          isActive
            ? 'bg-sidebar-selected text-sidebar-selected-foreground font-semibold before:absolute before:-left-3 before:top-1.5 before:bottom-1.5 before:w-[3px] before:rounded-r-full before:bg-sidebar-indicator'
            : 'text-sidebar-muted hover:bg-sidebar-hover hover:text-sidebar-foreground',
        )
      }
    >
      {({ isActive }) => (
        <>
          <item.icon
            className={cn(
              'h-5 w-5 flex-shrink-0',
              isActive ? 'text-sidebar-selected-foreground' : 'text-sidebar-muted',
            )}
          />
          {item.label}
        </>
      )}
    </NavLink>
  )
}

/** 사이드바 내용 — PC 고정 사이드바와 모바일 서랍(Sheet)이 같은 것을 쓴다. */
function SidebarContent({ onNavigate }: { onNavigate?: () => void }) {
  const { user } = useAuthStore()
  const logoutMutation = useLogout()
  const { theme, setTheme } = useSidebarTheme()
  const [passwordOpen, setPasswordOpen] = useState(false)
  const [mfaOpen, setMfaOpen] = useState(false)
  // 외부 사용자(ADR-0039)는 허용된 메뉴만 보인다 — 감사위원회·세무·기장대리인. 최종 판정은 서버
  const nav = navigation
    .map((g) => ({ ...g, items: g.items.filter((it) => isPathAllowed(user, it.path)) }))
    .filter((g) => g.items.length > 0)
  const left = daysLeft(user)

  // **`can_write` 가 아니라 `tenant_roles` 로 본다** — can_write 는 external_auditor 판정이고
  // icfr_manager 판정이 아니다. 섞으면 메뉴는 열리는데 서버가 403 을 낸다.
  const isIcfrManager = isIcfrManagerForUser(user)
  const isLocked = (item: NavItem) => Boolean(item.requiresIcfrManager) && !isIcfrManager

  const groupLabels = navigation
    .map((g) => g.groupLabel)
    .filter((label): label is string => label !== null)
  // 접힘 상태는 이 브라우저에 저장한다(새로고침해도 유지). 저장소를 못 쓰면 전부 펼친 상태로 시작한다
  const [expandedGroups, setExpandedGroups] = useState<Record<string, boolean>>(() => {
    const all = Object.fromEntries(groupLabels.map((label) => [label, true]))
    try {
      const saved = JSON.parse(localStorage.getItem(NAV_GROUPS_KEY) ?? '{}') as Record<string, boolean>
      return { ...all, ...saved }
    } catch {
      return all
    }
  })
  useEffect(() => {
    try {
      localStorage.setItem(NAV_GROUPS_KEY, JSON.stringify(expandedGroups))
    } catch {
      /* 저장소를 못 쓰면(사생활 보호 모드 등) 이번 창에서만 유지 */
    }
  }, [expandedGroups])
  const toggleGroup = (label: string) => {
    setExpandedGroups((prev) => ({ ...prev, [label]: !prev[label] }))
  }
  const setAllGroups = (open: boolean) =>
    setExpandedGroups(Object.fromEntries(groupLabels.map((label) => [label, open])))
  const allOpen = groupLabels.every((label) => expandedGroups[label])

  return (
    <>
      {/* 로고 */}
      <div className="flex h-16 shrink-0 items-center gap-3 px-5">
        <LogoMark className="h-10 w-10 shadow-sm rounded-[11px]" />
        <div className="min-w-0 leading-tight">
          <p className="text-lg font-extrabold tracking-tight text-sidebar-foreground">ICFR</p>
          <p className="truncate text-xs font-medium text-sidebar-muted">내부회계관리시스템</p>
        </div>
      </div>

      {/* 네비게이션 */}
      <nav className="flex-1 px-3 pb-3 pt-1 space-y-1">
        <div className="flex justify-end px-1 pb-1">
          <button
            onClick={() => setAllGroups(!allOpen)}
            className="flex items-center gap-1 rounded px-1.5 py-0.5 text-xs text-sidebar-muted hover:bg-sidebar-hover hover:text-sidebar-foreground transition-colors"
            title={allOpen ? '모든 메뉴 그룹 접기' : '모든 메뉴 그룹 펼치기'}
          >
            {allOpen ? <ChevronsDownUp className="h-3 w-3" /> : <ChevronsUpDown className="h-3 w-3" />}
            {allOpen ? '전체 접기' : '전체 펼치기'}
          </button>
        </div>
        {nav.map((group, idx) =>
          group.groupLabel === null ? (
            <div key={idx} className="mb-3">
              {group.items.map((item) => (
                <NavRow key={item.path} item={item} locked={isLocked(item)} onNavigate={onNavigate} />
              ))}
            </div>
          ) : (
            <div key={idx} className="mb-3">
              <button
                onClick={() => toggleGroup(group.groupLabel!)}
                className="flex w-full items-center justify-between px-3 pb-1 pt-2.5 text-[0.8rem] font-bold tracking-wide text-sidebar-muted hover:text-sidebar-foreground transition-colors"
              >
                {group.groupLabel}
                {expandedGroups[group.groupLabel] ? (
                  <ChevronDown className="h-3 w-3" />
                ) : (
                  <ChevronRight className="h-3 w-3" />
                )}
              </button>

              {expandedGroups[group.groupLabel] && (
                <div className="space-y-0.5">
                  {group.items.map((item) => (
                    <NavRow key={item.path} item={item} locked={isLocked(item)} onNavigate={onNavigate} />
                  ))}
                </div>
              )}
            </div>
          )
        )}
      </nav>

      {/* 테마 — 개인 설정(localStorage). 회사 설정이 아니므로 백엔드가 없다.
          3종이 되면서 토글로는 "다음이 뭔지" 알 수 없어 선택형으로 바꿨다. */}
      <div className="flex shrink-0 items-center justify-between px-5 py-2.5 border-t border-sidebar-border">
        <p className="text-xs font-medium text-sidebar-muted">사이드바 색</p>
        <div className="flex gap-1.5" role="group" aria-label="사이드바 테마">
          {SIDEBAR_THEMES.map((t) => (
            <button
              key={t.value}
              onClick={() => setTheme(t.value)}
              aria-pressed={theme === t.value}
              aria-label={`사이드바 ${t.label}`}
              title={`${t.label} — 이 브라우저에만 저장됩니다`}
              className={cn(
                'h-5 w-5 rounded-full border transition-all',
                THEME_SWATCH[t.value],
                theme === t.value
                  ? 'ring-2 ring-sidebar-indicator ring-offset-2 ring-offset-sidebar'
                  : 'border-sidebar-border hover:scale-110',
              )}
            />
          ))}
        </div>
      </div>

      {/* 하단 사용자 영역 */}
      <div className="shrink-0 px-3 py-3 border-t border-sidebar-border pb-[max(0.75rem,env(safe-area-inset-bottom))]">
        {user && (
          <div className="flex items-center gap-3 rounded-lg px-2 py-1.5">
            <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-brand-from to-brand-to text-sm font-bold text-white shadow-sm">
              {initials(user.display_name)}
            </span>
            <div className="min-w-0 flex-1 leading-tight">
              <p className="truncate text-[0.95rem] font-semibold text-sidebar-foreground">{user.display_name}</p>
              <p className="truncate text-xs text-sidebar-muted">
                {user.external
                  ? `${user.external.organization} · ${left === 0 ? '오늘 종료' : `${left}일 남음`}`
                  : (ROLE_LABEL[user.role] ?? user.role)}
              </p>
            </div>
            <button
              onClick={() => setMfaOpen(true)}
              className={cn(
                'relative rounded-md p-1.5 hover:bg-sidebar-hover hover:text-sidebar-foreground transition-colors',
                user.mfa_enabled ? 'text-sidebar-muted' : 'text-amber-500',
              )}
              title={user.mfa_enabled ? '2단계 인증 사용 중' : '2단계 인증 등록'}
              aria-label="2단계 인증"
            >
              <ShieldCheck className="h-4 w-4" />
              {!user.mfa_enabled && <span className="absolute right-1 top-1 h-1.5 w-1.5 rounded-full bg-amber-500" />}
            </button>
            <button
              onClick={() => setPasswordOpen(true)}
              className="rounded-md p-1.5 text-sidebar-muted hover:bg-sidebar-hover hover:text-sidebar-foreground transition-colors"
              title="비밀번호 변경"
              aria-label="비밀번호 변경"
            >
              <KeyRound className="h-4 w-4" />
            </button>
            <button
              onClick={() => logoutMutation.mutate()}
              className="rounded-md p-1.5 text-sidebar-muted hover:bg-sidebar-hover hover:text-sidebar-foreground transition-colors"
              title="로그아웃"
              aria-label="로그아웃"
            >
              <LogOut className="h-4 w-4" />
            </button>
          </div>
        )}
        <ChangePasswordDialog open={passwordOpen} onOpenChange={setPasswordOpen} />
        <MfaDialog open={mfaOpen} onOpenChange={setMfaOpen} />
      </div>
    </>
  )
}

/**
 * 앱 뼈대 — PC(md 이상): 왼쪽 고정 사이드바 + 상단 바(앱 설치). 모바일: 상단 바의 햄버거로 여는 서랍 메뉴.
 * 본문은 `min-w-0` 이라 넓은 표가 화면을 밀지 않고 표 자신이 가로 스크롤한다.
 */
export default function AppLayout() {
  useMe()
  const { theme } = useSidebarTheme()
  const scrollRef = useRef<HTMLElement | null>(null)
  const [drawer, setDrawer] = useState(false)
  const location = useLocation()
  // 저장된 값을 최초 렌더에서 DOM 에 반영한다 — store 초기값은 localStorage 에서 읽지만
  // `data-sidebar-theme` 속성은 아직 붙어 있지 않다(새로고침 직후).
  useEffect(() => applySidebarTheme(theme), [theme])
  useEffect(() => setDrawer(false), [location.pathname])
  const title = currentTitle(location.pathname)
  const helpOpen = useHelpPanel((s) => s.open)
  const toggleHelp = useHelpPanel((s) => s.toggle)

  // F1 = 도움말 열기/닫기. 입력 중 타이핑과 겹치지 않는 키라 입력칸에서도 그대로 둔다
  // (브라우저 기본 도움말만 막는다).
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== 'F1' || e.ctrlKey || e.altKey || e.metaKey) return
      e.preventDefault()
      toggleHelp()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [toggleHelp])

  // 스크롤바는 평소 숨기고 **스크롤 중에만** 보인다. 호버만으로는 휠을 굴리는 동안
  // 보이지 않아서, 스크롤 이벤트로 클래스를 잠깐 붙인다(CSS 만으로는 불가능하다).
  useEffect(() => {
    const el = scrollRef.current
    if (!el) return
    let timer: number | undefined
    const onScroll = () => {
      el.classList.add('is-scrolling')
      window.clearTimeout(timer)
      timer = window.setTimeout(() => el.classList.remove('is-scrolling'), 700)
    }
    el.addEventListener('scroll', onScroll, { passive: true })
    return () => {
      el.removeEventListener('scroll', onScroll)
      window.clearTimeout(timer)
    }
  }, [])

  return (
    <div className="flex min-h-screen bg-background">
      <aside
        ref={scrollRef}
        className="sidebar-scroll hidden w-72 flex-shrink-0 border-r border-sidebar-border bg-sidebar text-sidebar-foreground md:flex flex-col sticky top-0 h-screen overflow-y-auto"
      >
        <SidebarContent />
      </aside>

      <Sheet open={drawer} onOpenChange={setDrawer}>
        <SheetContent side="left" className="flex w-72 max-w-[85vw] flex-col overflow-y-auto border-sidebar-border bg-sidebar p-0 text-sidebar-foreground">
          <SheetTitle className="sr-only">메뉴</SheetTitle>
          <SidebarContent onNavigate={() => setDrawer(false)} />
        </SheetContent>
      </Sheet>

      <div className="flex min-w-0 flex-1 flex-col">
        {/* 상단 바 — 모바일: 메뉴·로고 / 모든 크기: 앱 설치·도움말 */}
        <header className="sticky top-0 z-30 flex h-14 items-center gap-2 border-b border-border/70 bg-background/85 px-3 pt-[env(safe-area-inset-top)] backdrop-blur-md supports-[backdrop-filter]:bg-background/70 md:px-8">
          <button
            type="button"
            onClick={() => setDrawer(true)}
            className="rounded-md p-2 hover:bg-muted md:hidden"
            aria-label="메뉴 열기"
          >
            <Menu className="h-5 w-5" />
          </button>
          <span className="flex items-center gap-2 md:hidden">
            <LogoMark className="h-7 w-7 rounded-lg" />
            <span className="font-extrabold tracking-tight">ICFR</span>
          </span>
          {title && <span className="hidden text-lg font-semibold text-foreground md:inline">{title}</span>}
          <div className="ml-auto flex items-center gap-2">
            <InstallButton />
            <button
              type="button"
              onClick={toggleHelp}
              aria-pressed={helpOpen}
              className={cn(
                'flex items-center gap-1.5 rounded-lg p-2 text-sm text-muted-foreground transition-colors hover:bg-card hover:text-foreground hover:shadow-card md:px-3 md:py-1.5',
                helpOpen && 'bg-card text-foreground font-medium shadow-card',
              )}
              aria-label="도움말 (F1)"
              title="도움말 (F1)"
            >
              <HelpCircle className="h-5 w-5 md:h-4 md:w-4" />
              <span className="hidden md:inline">도움말</span>
            </button>
          </div>
        </header>
        <main className="min-w-0 flex-1 overflow-x-hidden bg-background">
          <Outlet />
        </main>
      </div>

      {/* 매뉴얼 패널 — 넓은 화면은 본문을 밀고, 좁은 화면은 겹친다(features/help/HelpPanel) */}
      <HelpPanel />
    </div>
  )
}
