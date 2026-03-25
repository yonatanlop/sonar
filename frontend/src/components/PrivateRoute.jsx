import { Navigate, Outlet } from 'react-router-dom'
import { useAuthStore } from '../store/authStore'

export function PrivateRoute() {
  const isAuth = useAuthStore((s) => s.isAuth())
  return isAuth ? <Outlet /> : <Navigate to="/login" replace />
}

export function AdminRoute() {
  const isAdmin = useAuthStore((s) => s.isAdmin())
  const isAuth  = useAuthStore((s) => s.isAuth())
  if (!isAuth) return <Navigate to="/login" replace />
  if (!isAdmin) return <Navigate to="/" replace />
  return <Outlet />
}

export function AnalystRoute() {
  const isAnalyst = useAuthStore((s) => s.isAnalyst())
  const isAuth    = useAuthStore((s) => s.isAuth())
  if (!isAuth) return <Navigate to="/login" replace />
  if (!isAnalyst) return <Navigate to="/" replace />
  return <Outlet />
}
