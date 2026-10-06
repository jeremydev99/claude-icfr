import { Outlet } from 'react-router-dom'
import { ShieldCheck, Layers, FileCheck2 } from 'lucide-react'
import LogoMark from '@/components/brand/LogoMark'
import Illustration, { illustrationUrl } from '@/components/illustration/Illustration'

const POINTS = [
  { icon: Layers, text: '재무제표에서 스코핑·RCM까지 한 흐름으로' },
  { icon: ShieldCheck, text: '설계·운영평가와 미비점 개선을 한 곳에서' },
  { icon: FileCheck2, text: '운영실태 보고서를 실데이터로 바로 작성' },
]

const LOGIN_PHOTO = illustrationUrl('login-photo')

/**
 * 로그인 화면(대문) — 넓은 화면은 왼쪽 사진 패널(저녁 사무실, 남색 그라데이션 위에 문구) + 오른쪽 로그인 폼,
 * 좁은 화면(모바일)은 로고와 폼만. 사진 파일이 없으면 기존 3D 일러스트 패널로 그린다.
 */
export default function AuthLayout() {
  return (
    <div className="grid min-h-screen bg-background lg:grid-cols-[1.25fr_1fr]">
      <aside className="relative hidden overflow-hidden bg-[hsl(224_45%_9%)] text-white lg:flex lg:flex-col">
        {LOGIN_PHOTO ? (
          <>
            <img src={LOGIN_PHOTO} alt="" aria-hidden draggable={false} fetchPriority="high"
              className="absolute inset-0 h-full w-full select-none object-cover object-[70%_center]" />
            {/* 왼쪽 글자 자리를 남색으로 깊게, 오른쪽 인물은 살린다 */}
            <div className="absolute inset-0 bg-gradient-to-r from-[hsl(224_45%_8%/0.94)] via-[hsl(224_45%_8%/0.62)] to-[hsl(224_45%_8%/0.08)]" />
            <div className="absolute inset-x-0 bottom-0 h-1/3 bg-gradient-to-t from-[hsl(224_45%_8%/0.85)] to-transparent" />
          </>
        ) : (
          <>
            <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top_left,hsl(223_38%_34%/0.55),transparent_55%),radial-gradient(ellipse_at_bottom_right,hsl(220_24%_46%/0.35),transparent_55%)]" />
            <div className="absolute inset-0 flex items-center justify-center px-12">
              <Illustration slot="login-hero" eager
                className="aspect-[4/5] w-full max-w-[440px] [mask-image:radial-gradient(ellipse_at_center,black_55%,transparent_78%)]" />
            </div>
          </>
        )}

        <div className="relative z-10 flex flex-1 flex-col justify-center px-14 xl:px-20">
          <div className="flex items-center gap-3">
            <LogoMark className="h-11 w-11 rounded-xl shadow-lg" />
            <div className="leading-tight">
              <p className="text-lg font-extrabold tracking-tight">ICFR</p>
              <p className="text-xs text-white/70">내부회계관리시스템</p>
            </div>
          </div>
          <h1 className="mt-8 max-w-[520px] text-[40px] font-extrabold leading-[1.2] tracking-tight drop-shadow-sm xl:text-[46px]">
            내부회계관리제도를<br />더 정확하고 가볍게.
          </h1>
          <p className="mt-4 max-w-[460px] text-[17px] leading-relaxed text-white/80">
            스코핑부터 통제 평가, 미비점 개선, 이사회 보고까지 — 한 흐름으로 관리합니다.
          </p>
          <ul className="mt-8 space-y-3 text-[15px] text-white/85">
            {POINTS.map((p) => (
              <li key={p.text} className="flex items-center gap-3">
                <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-white/10 ring-1 ring-white/20 backdrop-blur-sm">
                  <p.icon className="h-4 w-4" />
                </span>
                {p.text}
              </li>
            ))}
          </ul>
        </div>
        <p className="relative z-10 px-14 pb-10 text-xs text-white/55 xl:px-20">© {new Date().getFullYear()} ICFR · 사내 전용 시스템</p>
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
        <p className="mt-10 text-xs text-muted-foreground lg:hidden">© {new Date().getFullYear()} ICFR · 사내 전용 시스템</p>
      </main>
    </div>
  )
}
