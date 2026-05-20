import { Outlet, NavLink } from 'react-router-dom'
import {
  LayoutDashboard,
  Calendar,
  FileText,
  Target,
  Database,
  Info,
  TrendingDown,
  LogOut,
} from 'lucide-react'
import { useAuthStore } from '@/features/auth/store'
import { useLogout, useMe } from '@/features/auth/hooks/useAuth'
import { cn } from '@/lib/utils'

const navItems = [
  { to: '/dashboard', label: '대시보드', icon: LayoutDashboard },
  { to: '/schedule', label: '일정관리', icon: Calendar },
  { to: '/rcm', label: 'RCM', icon: FileText },
  { to: '/scoping', label: 'Scoping', icon: Target },
  { to: '/euc', label: 'EUC', icon: Database },
  { to: '/iuc', label: 'IUC', icon: Info },
  { to: '/remediation', label: '개선계획', icon: TrendingDown },
]

export default function AppLayout() {
  const { user } = useAuthStore()
  const logoutMutation = useLogout()
  useMe()

  return (
    <div className="flex h-screen bg-background">
      <aside className="w-60 flex-shrink-0 border-r bg-card flex flex-col">
        <div className="p-4 border-b">
          <h1 className="text-xl font-bold text-primary">ICFR</h1>
        </div>

        <nav className="flex-1 p-2 space-y-1">
          {navItems.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                cn(
                  'flex items-center gap-3 px-3 py-2 rounded-md text-sm transition-colors',
                  isActive
                    ? 'bg-primary text-primary-foreground'
                    : 'text-muted-foreground hover:bg-accent hover:text-accent-foreground'
                )
              }
            >
              <Icon className="h-4 w-4" />
              {label}
            </NavLink>
          ))}
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
