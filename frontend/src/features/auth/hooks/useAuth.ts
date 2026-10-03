import { useMutation, useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import apiClient from '@/lib/axios'
import { useAuthStore, type UserProfile } from '../store'
import { LOGIN_TIMEOUT_MS } from '../loginError.pure'

/** 로그인 결과(ADR-0039) — MFA 대상이면 토큰 대신 `mfa_token` 과 다음 단계가 온다 */
export interface LoginResult {
  access_token: string | null
  refresh_token: string | null
  mfa_required: boolean
  mfa_setup_required: boolean
  mfa_token: string | null
}

/** 토큰을 받은 뒤 공통 마무리 — 저장 → /me → 대시보드 */
export function useFinishLogin() {
  const { setTokens, setUser } = useAuthStore()
  const navigate = useNavigate()
  return async (access: string, refresh: string) => {
    setTokens(access, refresh)
    const meResponse = await apiClient.get<UserProfile>('/api/auth/me', { timeout: LOGIN_TIMEOUT_MS })
    setUser(meResponse.data)
    navigate('/dashboard')
  }
}

export function useMfaVerify() {
  const finish = useFinishLogin()
  return useMutation({
    mutationFn: async (body: { mfa_token: string; code: string }) =>
      (await apiClient.post<LoginResult>('/api/auth/mfa/verify', body, { timeout: LOGIN_TIMEOUT_MS })).data,
    onSuccess: async (data) => {
      if (data.access_token && data.refresh_token) await finish(data.access_token, data.refresh_token)
    },
  })
}

export function useLogin() {
  const finish = useFinishLogin()

  return useMutation({
    mutationFn: async (credentials: { email: string; password: string }) => {
      const params = new URLSearchParams()
      params.append('username', credentials.email)
      params.append('password', credentials.password)
      const response = await apiClient.post('/api/auth/login', params, {
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        // 서버에 닿지 못하면(사외망 차단 등) 한없이 기다리지 않고 15초 뒤 실패로 알린다
        timeout: LOGIN_TIMEOUT_MS,
      })
      return response.data as LoginResult
    },
    onSuccess: async (data) => {
      // MFA 대상이면 여기서 끝나지 않는다 — 화면이 다음 단계(코드 입력·등록)를 그린다
      if (data.access_token && data.refresh_token) await finish(data.access_token, data.refresh_token)
    },
  })
}

export function useMe() {
  const { accessToken, setUser } = useAuthStore()

  return useQuery({
    queryKey: ['me'],
    queryFn: async () => {
      const response = await apiClient.get<UserProfile>('/api/auth/me')
      setUser(response.data)
      return response.data
    },
    enabled: !!accessToken,
  })
}

export function useLogout() {
  const { logout } = useAuthStore()
  const navigate = useNavigate()

  return useMutation({
    mutationFn: async () => {
      await apiClient.post('/api/auth/logout')
    },
    onSettled: () => {
      logout()
      navigate('/login')
    },
  })
}
