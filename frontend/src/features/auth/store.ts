import { create } from 'zustand'

export interface UserProfile {
  id: string
  email: string
  display_name: string
  role: string
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
