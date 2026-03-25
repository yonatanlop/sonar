import axios from 'axios'
import toast from 'react-hot-toast'

const client = axios.create({
  baseURL: '/api/v1',
  headers: { 'Content-Type': 'application/json' },
})

// Adjuntar token en cada request
client.interceptors.request.use((config) => {
  const token = localStorage.getItem('sonar_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// Manejar errores globalmente
client.interceptors.response.use(
  (res) => res,
  (error) => {
    const status = error.response?.status
    const detail = error.response?.data?.detail

    if (status === 401) {
      localStorage.removeItem('sonar_token')
      localStorage.removeItem('sonar_user')
      window.location.href = '/login'
      return Promise.reject(error)
    }

    if (status === 403) {
      toast.error('No tienes permisos para realizar esta acción')
    } else if (status >= 500) {
      toast.error('Error interno del servidor')
    } else if (detail) {
      toast.error(detail)
    }

    return Promise.reject(error)
  }
)

export default client
