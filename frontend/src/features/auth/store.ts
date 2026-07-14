import { create } from 'zustand'

export interface TenantSummary {
  id: string
  name: string
  code: string
  role: string
}

export interface UserProfile {
  id: string
  email: string
  display_name: string
  role: string
  tenants: TenantSummary[]
  active_tenant_id: string | null
}

interface AuthState {
  accessToken: string | null
  refreshToken: string | null
  user: UserProfile | null
  setTokens: (access: string, refresh: string) => void
  setUser: (user: UserProfile) => void
  logout: () => void
}

export const useAuthStore = create<AuthState>((set) => ({
  accessToken: localStorage.getItem('access_token'),
  refreshToken: localStorage.getItem('refresh_token'),
  user: null,
  setTokens: (access, refresh) => {
    localStorage.setItem('access_token', access)
    localStorage.setItem('refresh_token', refresh)
    set({ accessToken: access, refreshToken: refresh })
  },
  setUser: (user) => set({ user }),
  logout: () => {
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    set({ accessToken: null, refreshToken: null, user: null })
  },
}))

// 활성 tenant는 오직 /me 응답(user.active_tenant_id)에서만 파생한다 — 별도 저장소 없음.
export function useActiveTenantId(): string | null {
  return useAuthStore((s) => s.user?.active_tenant_id ?? null)
}
