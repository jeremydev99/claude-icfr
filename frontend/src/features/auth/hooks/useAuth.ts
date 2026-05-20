import { useMutation, useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import apiClient from '@/lib/axios'
import { useAuthStore, type UserProfile } from '../store'

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
      })
      return response.data
    },
    onSuccess: async (data) => {
      setTokens(data.access_token, data.refresh_token)
      const meResponse = await apiClient.get<UserProfile>('/api/auth/me')
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
