import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import { UserCircle, Lock } from 'lucide-react'
import { useAuthStore } from '../../../shared/store/authStore'
import { authApi } from '../../../shared/api/auth'

export default function Profile() {
  const { user } = useAuthStore()
  const [cur, setCur]   = useState('')
  const [next, setNext] = useState('')
  const [conf, setConf] = useState('')

  const changePwd = useMutation({
    mutationFn: () => authApi.changePassword(cur, next),
    onSuccess: () => { toast.success('Contraseña actualizada'); setCur(''); setNext(''); setConf('') },
    onError:   (e) => toast.error(e?.response?.data?.detail ?? 'Error al cambiar contraseña'),
  })

  const handleSubmit = (e) => {
    e.preventDefault()
    if (next !== conf) { toast.error('Las contraseñas no coinciden'); return }
    if (next.length < 6) { toast.error('Mínimo 6 caracteres'); return }
    changePwd.mutate()
  }

  const ROLE_LABEL = { admin: 'Administrador', analyst: 'Analista', viewer: 'Consulta' }

  return (
    <div className="space-y-6 max-w-lg">
      <h1 className="text-2xl font-bold text-gray-900">Mi perfil</h1>

      <div className="card flex items-center gap-4">
        <div className="w-14 h-14 rounded-full bg-primary-600 flex items-center justify-center text-white text-2xl font-bold">
          {user?.full_name?.charAt(0)?.toUpperCase() ?? 'U'}
        </div>
        <div>
          <p className="font-semibold text-gray-900 text-lg">{user?.full_name}</p>
          <p className="text-gray-500 text-sm">@{user?.username}</p>
          <span className="badge badge-low mt-1">{ROLE_LABEL[user?.role]}</span>
        </div>
      </div>

      <div className="card">
        <div className="flex items-center gap-2 mb-4">
          <Lock className="w-4 h-4 text-gray-500" />
          <h2 className="font-semibold text-gray-800">Cambiar contraseña</h2>
        </div>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="label">Contraseña actual</label>
            <input className="input" type="password" value={cur} onChange={e => setCur(e.target.value)} />
          </div>
          <div>
            <label className="label">Nueva contraseña</label>
            <input className="input" type="password" value={next} onChange={e => setNext(e.target.value)} />
          </div>
          <div>
            <label className="label">Confirmar nueva contraseña</label>
            <input className="input" type="password" value={conf} onChange={e => setConf(e.target.value)} />
          </div>
          <button type="submit" className="btn-primary" disabled={changePwd.isPending}>
            {changePwd.isPending ? 'Guardando...' : 'Guardar cambios'}
          </button>
        </form>
      </div>
    </div>
  )
}
