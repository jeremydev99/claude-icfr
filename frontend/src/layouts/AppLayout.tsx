import { useState } from 'react'
import { Outlet, NavLink } from 'react-router-dom'
import { ChevronDown, ChevronRight, LogOut } from 'lucide-react'
import { useAuthStore } from '@/features/auth/store'
import { useLogout, useMe } from '@/features/auth/hooks/useAuth'
import { cn } from '@/lib/utils'
import { navigation } from '@/config/navigation'

export default function AppLayout() {
  const { user } = useAuthStore()
  const logoutMutation = useLogout()
  useMe()

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
      <aside className="w-60 flex-shrink-0 border-r border-border bg-sidebar flex flex-col sticky top-0 h-screen overflow-y-auto">
        {/* 로고 */}
        <div className="px-5 py-4 border-b border-border">
          <h1 className="text-lg font-bold tracking-tight text-primary">ICFR</h1>
          <p className="text-[10px] text-muted-foreground mt-0.5 tracking-wide uppercase">내부회계관리시스템</p>
        </div>

        {/* 네비게이션 */}
        <nav className="flex-1 px-3 py-3 space-y-1">
          {navigation.map((group, idx) =>
            group.groupLabel === null ? (
              <div key={idx} className="mb-3">
                {group.items.map((item) => (
                  <NavLink
                    key={item.path}
                    to={item.path}
                    className={({ isActive }) =>
                      cn(
                        'flex items-center gap-2.5 px-3 py-2 rounded-md text-sm transition-colors',
                        isActive
                          ? 'bg-primary text-primary-foreground font-medium'
                          : 'text-muted-foreground hover:bg-accent hover:text-foreground'
                      )
                    }
                  >
                    {({ isActive }) => (
                      <>
                        <item.icon className={cn('h-4 w-4 flex-shrink-0', isActive ? 'text-primary-foreground' : 'text-muted-foreground')} />
                        {item.label}
                      </>
                    )}
                  </NavLink>
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
                      <NavLink
                        key={item.path}
                        to={item.path}
                        className={({ isActive }) =>
                          cn(
                            'flex items-center gap-2.5 px-3 py-2 rounded-md text-sm transition-colors',
                            isActive
                              ? 'bg-primary text-primary-foreground font-medium'
                              : 'text-muted-foreground hover:bg-accent hover:text-foreground'
                          )
                        }
                      >
                        {({ isActive }) => (
                          <>
                            <item.icon className={cn('h-4 w-4 flex-shrink-0', isActive ? 'text-primary-foreground' : 'text-muted-foreground')} />
                            {item.label}
                          </>
                        )}
                      </NavLink>
                    ))}
                  </div>
                )}
              </div>
            )
          )}
        </nav>

        {/* 하단 사용자 영역 */}
        <div className="px-4 py-3 border-t border-border">
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
