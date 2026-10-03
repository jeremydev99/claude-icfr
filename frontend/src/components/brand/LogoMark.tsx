import { useId } from 'react'
import { cn } from '@/lib/utils'

/**
 * ICFR 로고 마크 — 2×2 격자(I C / F R)를 브랜드 그라데이션 타일 위에 얹는다.
 * 파비콘(public/favicon.svg)과 같은 구성이라 탭·설치 아이콘·화면 로고가 한 모양으로 읽힌다.
 * 그라데이션 id 는 한 화면에 여러 번 그려져도 겹치지 않게 useId 로 만든다.
 */
export default function LogoMark({ className }: { className?: string }) {
  const id = useId().replace(/:/g, '')
  return (
    <svg viewBox="0 0 64 64" className={cn('h-8 w-8 shrink-0', className)} aria-hidden="true">
      <defs>
        <linearGradient id={`lg-${id}`} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="hsl(224 80% 50%)" />
          <stop offset="1" stopColor="hsl(199 89% 48%)" />
        </linearGradient>
      </defs>
      <rect width="64" height="64" rx="15" fill={`url(#lg-${id})`} />
      <rect x="1" y="1" width="62" height="62" rx="14" fill="none" stroke="white" strokeOpacity="0.18" />
      <g fill="#fff" fontFamily="'Pretendard Variable', 'Segoe UI', Arial, sans-serif" fontSize="23" fontWeight="800"
        textAnchor="middle" dominantBaseline="central">
        <text x="20" y="20.5">I</text>
        <text x="44" y="20.5">C</text>
        <text x="20" y="44.5">F</text>
        <text x="44" y="44.5">R</text>
      </g>
    </svg>
  )
}
