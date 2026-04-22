import { create } from 'zustand'
import { authApi } from '../api/auth'

const decodePayload = (token) => {
  try { return JSON.parse(atob(token.split('.')[1])) } catch { return null }
}

const isExpired = (token) => {
  if (!token) return true
  const p = decodePayload(token)
  if (!p?.exp) return true
  return Date.now() / 1000 > p.exp - 10
}

const storedUser = () => {
  try { return JSON.parse(localStorage.getItem('sonar_user')) } catch { return null }
}

export const useAuthStore = create((set, get) => ({
  user:    storedUser(),
  token:   localStorage.getItem('sonar_token'),
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

  logout: () => {
    localStorage.removeItem('sonar_token')
    localStorage.removeItem('sonar_user')
    set({ user: null, token: null })
  },

  setUser: (user) => {
    localStorage.setItem('sonar_user', JSON.stringify(user))
    set({ user })
  },

  isAdmin:   () => get().user?.role === 'admin',
  isAnalyst: () => ['admin', 'analyst'].includes(get().user?.role),

  isAuth: () => {
    const token = get().token
    if (!token) return false
    if (isExpired(token)) {
      localStorage.removeItem('sonar_token')
      localStorage.removeItem('sonar_user')
      set({ user: null, token: null })
      return false
    }
    return true
  },
}))
