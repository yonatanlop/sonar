import { Navigate, Outlet } from 'react-router-dom'
import { useAuthStore } from '../store/authStore'

export function PrivateRoute() {
  const isAuth = useAuthStore((s) => s.isAuth())
  return isAuth ? <Outlet /> : <Navigate to="/login" replace />
}

export function AdminRoute() {
  const isAuth  = useAuthStore((s) => s.isAuth())
  const isAdmin = useAuthStore((s) => s.isAdmin())
  if (!isAuth)  return <Navigate to="/login" replace />
  if (!isAdmin) return <Navigate to="/" replace />
  return <Outlet />
}

export function AnalystRoute() {
  const isAuth    = useAuthStore((s) => s.isAuth())
  const isAnalyst = useAuthStore((s) => s.isAnalyst())
  if (!isAuth)    return <Navigate to="/login" replace />
  if (!isAnalyst) return <Navigate to="/" replace />
  return <Outlet />
}
