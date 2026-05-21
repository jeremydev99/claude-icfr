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
      <aside className="w-60 flex-shrink-0 border-r bg-card flex flex-col sticky top-0 h-screen overflow-y-auto">
        <div className="p-4 border-b">
          <h1 className="text-xl font-bold text-primary">ICFR</h1>
        </div>

        <nav className="flex-1 p-2">
          {navigation.map((group, idx) =>
            group.groupLabel === null ? (
              <div key={idx} className="mb-2">
                {group.items.map((item) => (
                  <NavLink
                    key={item.path}
                    to={item.path}
                    className={({ isActive }) =>
                      cn(
                        'flex items-center gap-3 px-3 py-2 rounded-md text-sm transition-colors',
                        isActive
                          ? 'bg-accent text-accent-foreground font-medium'
                          : 'text-muted-foreground hover:bg-accent hover:text-accent-foreground'
                      )
                    }
                  >
                    <item.icon className="h-4 w-4 flex-shrink-0" />
                    {item.label}
                  </NavLink>
                ))}
              </div>
            ) : (
              <div key={idx} className="mb-1">
                <button
                  onClick={() => toggleGroup(group.groupLabel!)}
                  className="flex w-full items-center justify-between px-3 py-1.5 text-xs font-semibold uppercase tracking-wider text-muted-foreground hover:text-foreground transition-colors"
                >
                  {group.groupLabel}
                  {expandedGroups[group.groupLabel] ? (
                    <ChevronDown className="h-3 w-3" />
                  ) : (
                    <ChevronRight className="h-3 w-3" />
                  )}
                </button>

                {expandedGroups[group.groupLabel] && (
                  <div className="mt-0.5 mb-2 space-y-0.5">
                    {group.items.map((item) => (
                      <NavLink
                        key={item.path}
                        to={item.path}
                        className={({ isActive }) =>
                          cn(
                            'flex items-center gap-3 px-3 py-2 rounded-md text-sm transition-colors',
                            isActive
                              ? 'bg-accent text-accent-foreground font-medium'
                              : 'text-muted-foreground hover:bg-accent hover:text-accent-foreground'
                          )
                        }
                      >
                        <item.icon className="h-4 w-4 flex-shrink-0 text-muted-foreground" />
                        {item.label}
                      </NavLink>
                    ))}
                  </div>
                )}
              </div>
            )
          )}
        </nav>

        <div className="p-4 border-t">
          {user && (
            <div className="mb-2">
              <p className="text-sm font-medium">{user.display_name}</p>
              <p className="text-xs text-muted-foreground">{user.role}</p>
            </div>
          )}
          <button
            onClick={() => logoutMutation.mutate()}
            className="flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground transition-colors"
          >
            <LogOut className="h-4 w-4" />
            로그아웃
          </button>
        </div>
      </aside>

      <main className="flex-1 overflow-auto">
        <Outlet />
      </main>
    </div>
  )
}
