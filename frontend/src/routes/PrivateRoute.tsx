import { Navigate } from 'react-router-dom'
import { useAuthStore } from '@/features/auth/store'

interface PrivateRouteProps {
  children: React.ReactNode
}

export default function PrivateRoute({ children }: PrivateRouteProps) {
  const { accessToken } = useAuthStore()

  if (!accessToken) {
    return <Navigate to="/login" replace />
  }

  return <>{children}</>
}
