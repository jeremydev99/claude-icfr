import { Link } from 'react-router-dom'
import { ArrowRight, CalendarDays } from 'lucide-react'
import { useAuthStore } from '@/features/auth/store'
import Illustration from '@/components/illustration/Illustration'

/** 시간대 인사 — 순수 계산 */
export function greeting(hour: number): string {
  if (hour < 5) return '늦은 시간까지 수고 많으십니다'
  if (hour < 12) return '좋은 아침입니다'
  if (hour < 18) return '좋은 오후입니다'
  return '오늘도 수고 많으셨습니다'
}

/** 대시보드 맨 위 환영 배너 — 인사·오늘 날짜·바로가기 + 오른쪽 일러스트. */
export default function WelcomeHero() {
  const user = useAuthStore((s) => s.user)
  const now = new Date()
  const today = now.toLocaleDateString('ko-KR', { year: 'numeric', month: 'long', day: 'numeric', weekday: 'long' })
  return (
    <section className="relative overflow-hidden rounded-2xl border border-border/70 bg-card shadow-card">
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top_left,hsl(var(--brand-from)/0.10),transparent_60%),radial-gradient(ellipse_at_bottom_right,hsl(var(--brand-to)/0.10),transparent_55%)]" />
      {/* 배너 오른쪽 그림 — 왼쪽은 글자 자리라 그림이 오른쪽에 몰려 있다. 좁은 화면에서는 숨긴다 */}
      <Illustration slot="dashboard-hero"
        className="pointer-events-none absolute inset-y-0 right-0 hidden h-full w-[62%] object-cover object-right md:block [mask-image:linear-gradient(to_right,transparent,black_35%)]" />
      <div className="relative grid items-center gap-4 p-6 md:grid-cols-[1fr_auto] md:p-8">
        <div className="min-w-0">
          <p className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
            <CalendarDays className="h-3.5 w-3.5" /> {today}
          </p>
          <h1 className="mt-2 text-2xl font-bold tracking-tight md:text-[28px]">
            {greeting(now.getHours())}{user ? `, ${user.display_name}님` : ''}
          </h1>
          <p className="mt-1.5 max-w-xl text-sm text-muted-foreground">
            내부회계관리제도 진행 현황입니다. 각 카드를 눌러 해당 업무로 바로 이동할 수 있습니다.
          </p>
          <div className="mt-4 flex flex-wrap gap-2">
            {[
              { to: '/scoping', label: '스코핑' },
              { to: '/rcm', label: 'RCM 관리' },
              { to: '/test', label: '평가(Test)' },
              { to: '/report', label: 'Report' },
            ].map((l) => (
              <Link key={l.to} to={l.to}
                className="inline-flex items-center gap-1 rounded-full border bg-background/70 px-3 py-1.5 text-xs font-medium text-foreground transition-colors hover:border-primary/40 hover:bg-accent hover:text-accent-foreground">
                {l.label} <ArrowRight className="h-3 w-3" />
              </Link>
            ))}
          </div>
        </div>
        <div className="hidden md:block md:w-[220px] lg:w-[300px]" aria-hidden="true" />
      </div>
    </section>
  )
}
