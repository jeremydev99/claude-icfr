import axios from 'axios'
import { useAuthStore } from '@/features/auth/store'

const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000',
})

apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// tenant 확정 전(로그인/토큰갱신/최초 /me) 요청은 제외 — 헤더가 붙어도 무해하지만 명시적으로 뺀다.
const TENANT_HEADER_EXCLUDED_PATHS = ['/auth/login', '/auth/refresh', '/auth/me']

apiClient.interceptors.request.use((config) => {
  const url = config.url ?? ''
  const isExcluded = TENANT_HEADER_EXCLUDED_PATHS.some((path) => url.includes(path))
  if (isExcluded) return config

  const tenantId = useAuthStore.getState().user?.active_tenant_id ?? null
  if (tenantId) {
    config.headers['X-Tenant-Id'] = tenantId
  }
  return config
})

let isRefreshing = false
let failedQueue: Array<{
  resolve: (token: string) => void
  reject: (error: unknown) => void
}> = []

const processQueue = (error: unknown, token: string | null = null) => {
  failedQueue.forEach((prom) => {
    if (error) {
      prom.reject(error)
    } else {
      prom.resolve(token!)
    }
  })
  failedQueue = []
}

apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config

    if (error.response?.status === 401 && !originalRequest._retry) {
      if (isRefreshing) {
        return new Promise((resolve, reject) => {
          failedQueue.push({ resolve, reject })
        })
          .then((token) => {
            originalRequest.headers.Authorization = `Bearer ${token}`
            return apiClient(originalRequest)
          })
          .catch((err) => Promise.reject(err))
      }

      originalRequest._retry = true
      isRefreshing = true

      const refreshToken = localStorage.getItem('refresh_token')
      if (!refreshToken) {
        localStorage.clear()
        window.location.href = '/login'
        return Promise.reject(error)
      }

      try {
        const response = await axios.post(
          `${import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'}/api/auth/refresh`,
          { refresh_token: refreshToken }
        )
        const newAccessToken = response.data.access_token
        localStorage.setItem('access_token', newAccessToken)
        processQueue(null, newAccessToken)
        originalRequest.headers.Authorization = `Bearer ${newAccessToken}`
        return apiClient(originalRequest)
      } catch (refreshError) {
        processQueue(refreshError, null)
        localStorage.clear()
        window.location.href = '/login'
        return Promise.reject(refreshError)
      } finally {
        isRefreshing = false
      }
    }

    return Promise.reject(error)
  }
)

export default apiClient
