import { Navigate } from 'react-router-dom'
import { useAuthStore } from '@/features/auth/store'
import type { UserProfile } from '@/features/auth/store'

interface RoleRouteProps {
  /** 들어올 수 있는가 — `features/auth/permissions.pure.ts` 의 판정 함수를 넘긴다 */
  allow: (user: UserProfile | null | undefined) => boolean
  /** 막혔을 때 보낼 곳 */
  fallback: string
  children: React.ReactNode
}

/**
 * 역할 라우트 가드(2026-10-16, 조사 4) — 메뉴를 잠가도 주소를 직접 치면 들어오던 것을 막는다.
 * 화면 편의일 뿐 최종 판정은 서버다. 프로필을 아직 못 받았으면 판정하지 않고 기다린다(새로고침 직후 튕김 방지).
 */
export default function RoleRoute({ allow, fallback, children }: RoleRouteProps) {
  const user = useAuthStore((s) => s.user)
  if (!user) return null
  if (!allow(user)) return <Navigate to={fallback} replace />
  return <>{children}</>
}
