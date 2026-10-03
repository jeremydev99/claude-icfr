import { Outlet } from 'react-router-dom'
import { ShieldCheck, Layers, FileCheck2 } from 'lucide-react'
import LogoMark from '@/components/brand/LogoMark'
import Illustration from '@/components/illustration/Illustration'

const POINTS = [
  { icon: Layers, text: '재무제표에서 스코핑·RCM까지 한 흐름으로' },
  { icon: ShieldCheck, text: '설계·운영평가와 미비점 개선을 한 곳에서' },
  { icon: FileCheck2, text: '운영실태 보고서를 실데이터로 바로 작성' },
]

/**
 * 로그인 화면 뼈대 — 넓은 화면은 왼쪽 브랜드 패널(일러스트·핵심 가치) + 오른쪽 로그인 폼,
 * 좁은 화면(모바일)은 로고와 폼만. 폼은 LoginForm 이 그린다.
 */
export default function AuthLayout() {
  return (
    <div className="grid min-h-screen bg-background lg:grid-cols-[1.05fr_1fr]">
      <aside className="relative hidden overflow-hidden bg-[hsl(225_52%_11%)] text-white lg:flex lg:flex-col">
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top_left,hsl(224_80%_50%/0.45),transparent_55%),radial-gradient(ellipse_at_bottom_right,hsl(199_89%_48%/0.35),transparent_55%)]" />
        <div className="relative z-10 flex items-center gap-3 px-12 pt-10">
          <LogoMark className="h-10 w-10 rounded-xl" />
          <div className="leading-tight">
            <p className="text-lg font-extrabold tracking-tight">ICFR</p>
            <p className="text-xs text-white/70">내부회계관리시스템</p>
          </div>
        </div>
        <div className="relative z-10 flex flex-1 items-center justify-center px-12">
          {/* 그림 가장자리를 패널 남색으로 서서히 사라지게 — 사각 경계가 보이지 않게 */}
          <Illustration slot="login-hero" eager
            className="aspect-[4/5] w-full max-w-[440px] [mask-image:radial-gradient(ellipse_at_center,black_55%,transparent_78%)]" />
        </div>
        <div className="relative z-10 px-12 pb-12">
          <h2 className="text-[28px] font-bold leading-snug tracking-tight">
            내부회계관리제도를<br />더 정확하고 가볍게.
          </h2>
          <ul className="mt-5 space-y-2.5 text-sm text-white/80">
            {POINTS.map((p) => (
              <li key={p.text} className="flex items-center gap-2.5">
                <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-white/10 ring-1 ring-white/15">
                  <p.icon className="h-4 w-4" />
                </span>
                {p.text}
              </li>
            ))}
          </ul>
        </div>
      </aside>

      <main className="flex flex-col items-center justify-center px-5 py-10 sm:px-10">
        <div className="mb-8 flex items-center gap-3 lg:hidden">
          <LogoMark className="h-10 w-10 rounded-xl" />
          <div className="leading-tight">
            <p className="text-lg font-extrabold tracking-tight">ICFR</p>
            <p className="text-xs text-muted-foreground">내부회계관리시스템</p>
          </div>
        </div>
        <Outlet />
        <p className="mt-10 text-xs text-muted-foreground">© {new Date().getFullYear()} ICFR · 사내 전용 시스템</p>
      </main>
    </div>
  )
}
