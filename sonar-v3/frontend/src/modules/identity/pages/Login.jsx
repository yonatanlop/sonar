import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Eye, EyeOff, Radio } from 'lucide-react'
import toast from 'react-hot-toast'
import { useAuthStore } from '../../../shared/store/authStore'

export default function Login() {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [showPwd, setShowPwd]   = useState(false)
  const { login, loading } = useAuthStore()
  const navigate = useNavigate()

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!username || !password) { toast.error('Ingresa usuario y contraseña'); return }
    try {
      await login(username, password)
      navigate('/')
    } catch { /* interceptor handles */ }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-primary-900 via-primary-700 to-primary-500 flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 bg-white/10 rounded-2xl backdrop-blur mb-4">
            <Radio className="w-8 h-8 text-white" />
          </div>
          <h1 className="text-3xl font-bold text-white tracking-tight">SONAR</h1>
          <p className="text-primary-200 text-sm mt-1">Sistema de Observación y Navegación en Ambientes de Redes</p>
        </div>

        <div className="bg-white rounded-2xl shadow-2xl p-8">
          <h2 className="text-xl font-semibold text-gray-800 mb-6">Iniciar sesión</h2>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="label">Usuario</label>
              <input className="input" type="text" placeholder="nombre.usuario"
                value={username} onChange={e => setUsername(e.target.value)}
                autoComplete="username" autoFocus />
            </div>
            <div>
              <label className="label">Contraseña</label>
              <div className="relative">
                <input className="input pr-10" type={showPwd ? 'text' : 'password'}
                  placeholder="••••••••" value={password}
                  onChange={e => setPassword(e.target.value)} autoComplete="current-password" />
                <button type="button" onClick={() => setShowPwd(!showPwd)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600">
                  {showPwd ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>
            <button type="submit" disabled={loading} className="btn-primary w-full justify-center py-2.5 mt-2">
              {loading ? 'Ingresando...' : 'Ingresar'}
            </button>
          </form>
          <p className="text-center text-xs text-gray-400 mt-6">Acceso restringido — Solo personal autorizado</p>
        </div>

        <p className="text-center text-primary-300 text-xs mt-6">SONAR v3.0 · Arquitectura Hexagonal</p>
      </div>
    </div>
  )
}
