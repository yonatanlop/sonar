import { create } from 'zustand'
import { authApi } from '../api/auth'

// ── Helpers JWT (decodificación client-side, sin verificar firma) ──

const decodeTokenPayload = (token) => {
  try {
    return JSON.parse(atob(token.split('.')[1]))
  } catch {
    return null
  }
}

const isTokenExpired = (token) => {
  if (!token) return true
  const payload = decodeTokenPayload(token)
  if (!payload?.exp) return true
  // Margen de 10 segundos para evitar race conditions
  return Date.now() / 1000 > payload.exp - 10
}

const stored = () => {
  try {
    return JSON.parse(localStorage.getItem('sonar_user'))
  } catch {
    return null
  }
}

export const useAuthStore = create((set, get) => ({
  user:  stored(),
  token: localStorage.getItem('sonar_token'),
  loading: false,

  login: async (username, password) => {
    set({ loading: true })
    try {
      const data = await authApi.login(username, password)
      localStorage.setItem('sonar_token', data.access_token)
      localStorage.setItem('sonar_user', JSON.stringify(data.user))
      set({ user: data.user, token: data.access_token, loading: false })
      return data.user
    } catch (err) {
      set({ loading: false })
      throw err
    }
  },

  logout: async () => {
    const token = get().token
    // Intentar invalidar token en el backend solo si aún es válido
    if (token && !isTokenExpired(token)) {
      try {
        await authApi.logout()
      } catch {
        // Si falla (ej: red caída), igual limpiamos el frontend
      }
    }
    localStorage.removeItem('sonar_token')
    localStorage.removeItem('sonar_user')
    set({ user: null, token: null })
  },

  // Limpia la sesión localmente sin llamar al backend (para tokens ya expirados)
  clearSession: () => {
    localStorage.removeItem('sonar_token')
    localStorage.removeItem('sonar_user')
    set({ user: null, token: null })
  },

  setUser: (user) => {
    localStorage.setItem('sonar_user', JSON.stringify(user))
    set({ user })
  },

  isAdmin:      () => get().user?.role === 'admin',
  isAnalyst:    () => ['admin', 'analyst'].includes(get().user?.role),
  isSuperAdmin: () => !!get().user?.is_superadmin,

  // Verifica existencia Y vigencia del token
  isAuth: () => {
    const token = get().token
    if (!token) return false
    if (isTokenExpired(token)) {
      // Limpiar silenciosamente sin llamar al backend (token ya inservible)
      localStorage.removeItem('sonar_token')
      localStorage.removeItem('sonar_user')
      set({ user: null, token: null })
      return false
    }
    return true
  },
}))
