import { useEffect, useState } from 'react'
import { Outlet, NavLink } from 'react-router-dom'
import { ChevronDown, ChevronRight, Lock, LogOut, Moon, Sun } from 'lucide-react'
import { useAuthStore } from '@/features/auth/store'
import { isIcfrManagerForUser } from '@/features/auth/permissions.pure'
import { useLogout, useMe } from '@/features/auth/hooks/useAuth'
import { applySidebarTheme, useSidebarTheme } from '@/features/admin/sidebarTheme'
import { cn } from '@/lib/utils'
import { navigation, type NavItem } from '@/config/navigation'

/** 메뉴 한 줄. 권한이 없으면 **숨기지 않고 잠근다** — 숨기면 "그런 기능이 있는지"조차 모른다. */
function NavRow({ item, locked }: { item: NavItem; locked: boolean }) {
  if (locked) {
    return (
      <div
        className="flex cursor-not-allowed items-center gap-2.5 rounded-md px-3 py-2 text-sm text-muted-foreground/50"
        title="내부회계관리자만 사용할 수 있습니다"
      >
        <item.icon className="h-4 w-4 flex-shrink-0" />
        <span className="flex-1">{item.label}</span>
        <Lock className="h-3 w-3 flex-shrink-0" />
      </div>
    )
  }
  return (
    <NavLink
      to={item.path}
      className={({ isActive }) =>
        cn(
          'flex items-center gap-2.5 px-3 py-2 rounded-md text-sm transition-colors',
          isActive
            ? 'bg-primary text-primary-foreground font-medium'
            : 'text-muted-foreground hover:bg-sidebar-hover hover:text-foreground',
        )
      }
    >
      {({ isActive }) => (
        <>
          <item.icon
            className={cn('h-4 w-4 flex-shrink-0', isActive ? 'text-primary-foreground' : 'text-muted-foreground')}
          />
          {item.label}
        </>
      )}
    </NavLink>
  )
}

export default function AppLayout() {
  const { user } = useAuthStore()
  const logoutMutation = useLogout()
  useMe()

  const { theme, setTheme } = useSidebarTheme()
  // 저장된 값을 최초 렌더에서 DOM 에 반영한다 — store 초기값은 localStorage 에서 읽지만
  // `data-sidebar-theme` 속성은 아직 붙어 있지 않다(새로고침 직후).
  useEffect(() => applySidebarTheme(theme), [theme])

  // **`can_write` 가 아니라 `tenant_roles` 로 본다** — can_write 는 external_auditor 판정이고
  // icfr_manager 판정이 아니다. 섞으면 메뉴는 열리는데 서버가 403 을 낸다.
  const isIcfrManager = isIcfrManagerForUser(user)
  const isLocked = (item: NavItem) => Boolean(item.requiresIcfrManager) && !isIcfrManager

  const groupLabels = navigation
    .map((g) => g.groupLabel)
    .filter((label): label is string => label !== null)

  const [expandedGroups, setExpandedGroups] = useState<Record<string, boolean>>(
    Object.fromEntries(groupLabels.map((label) => [label, true]))
  )

  const toggleGroup = (label: string) => {
    setExpandedGroups((prev) => ({ ...prev, [label]: !prev[label] }))
  }

  return (
    <div className="flex min-h-screen bg-background">
      <aside className="w-60 flex-shrink-0 border-r border-sidebar-border bg-sidebar flex flex-col sticky top-0 h-screen overflow-y-auto">
        {/* 로고 */}
        <div className="px-5 py-4 border-b border-sidebar-border">
          <h1 className="text-lg font-bold tracking-tight text-primary">ICFR</h1>
          <p className="text-[10px] text-muted-foreground mt-0.5 tracking-wide uppercase">내부회계관리시스템</p>
        </div>

        {/* 네비게이션 */}
        <nav className="flex-1 px-3 py-3 space-y-1">
          {navigation.map((group, idx) =>
            group.groupLabel === null ? (
              <div key={idx} className="mb-3">
                {group.items.map((item) => (
                  <NavRow key={item.path} item={item} locked={isLocked(item)} />
                ))}
              </div>
            ) : (
              <div key={idx} className="mb-3">
                <button
                  onClick={() => toggleGroup(group.groupLabel!)}
                  className="flex w-full items-center justify-between px-3 py-1 mb-0.5 text-[10px] font-semibold uppercase tracking-widest text-muted-foreground/70 hover:text-muted-foreground transition-colors"
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
                      <NavRow key={item.path} item={item} locked={isLocked(item)} />
                    ))}
                  </div>
                )}
              </div>
            )
          )}
        </nav>

        {/* 테마 — 개인 설정(localStorage). 회사 설정이 아니므로 백엔드가 없다 */}
        <div className="px-4 py-2 border-t border-sidebar-border">
          <button
            onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
            className="flex w-full items-center gap-2 rounded-md px-1 py-1.5 text-xs text-muted-foreground transition-colors hover:bg-sidebar-hover hover:text-foreground"
            title="사이드바 테마 전환 (이 브라우저에만 저장됩니다)"
          >
            {theme === 'dark' ? <Sun className="h-3.5 w-3.5" /> : <Moon className="h-3.5 w-3.5" />}
            {theme === 'dark' ? '라이트 테마' : '다크 테마'}
          </button>
        </div>

        {/* 하단 사용자 영역 */}
        <div className="px-4 py-3 border-t border-sidebar-border">
          {user && (
            <div className="mb-2.5">
              <p className="text-sm font-medium text-foreground leading-tight">{user.display_name}</p>
              <p className="text-xs text-muted-foreground mt-0.5">{user.role}</p>
            </div>
          )}
          <button
            onClick={() => logoutMutation.mutate()}
            className="flex items-center gap-2 text-xs text-muted-foreground hover:text-foreground transition-colors"
          >
            <LogOut className="h-3.5 w-3.5" />
            로그아웃
          </button>
        </div>
      </aside>

      <main className="flex-1 overflow-auto bg-background">
        <Outlet />
      </main>
    </div>
  )
}
