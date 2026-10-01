import { useMutation, useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import apiClient from '@/lib/axios'
import { useAuthStore, type UserProfile } from '../store'
import { LOGIN_TIMEOUT_MS } from '../loginError.pure'

export function useLogin() {
  const { setTokens, setUser } = useAuthStore()
  const navigate = useNavigate()

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
      return response.data
    },
    onSuccess: async (data) => {
      setTokens(data.access_token, data.refresh_token)
      const meResponse = await apiClient.get<UserProfile>('/api/auth/me', { timeout: LOGIN_TIMEOUT_MS })
      setUser(meResponse.data)
      navigate('/dashboard')
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
