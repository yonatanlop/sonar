import { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { User, Bell, Lock, CheckCircle2, Eye, EyeOff } from 'lucide-react'
import toast from 'react-hot-toast'
import { authApi } from '../api/auth'
import { useAuthStore } from '../store/authStore'

export default function Profile() {
  const qc         = useQueryClient()
  const setUser    = useAuthStore(s => s.setUser)

  const { data: me, isLoading } = useQuery({
    queryKey: ['me'],
    queryFn: authApi.getMe,
  })

  // ── Estado local del formulario personal ──
  const [info, setInfo] = useState({ full_name: '', email: '' })

  // ── Estado del formulario de notificaciones ──
  const [notif, setNotif] = useState({
    notify_telegram:  false,
    telegram_chat_id: '',
    notify_whatsapp:  false,
    whatsapp_phone:   '',
    whatsapp_api_key: '',
    notify_email:     true,
  })

  // ── Estado del formulario de contraseña ──
  const [pwd, setPwd]           = useState({ current: '', next: '', confirm: '' })
  const [showPwd, setShowPwd]   = useState(false)

  // Sincronizar estado con datos del servidor
  useEffect(() => {
    if (!me) return
    setInfo({ full_name: me.full_name ?? '', email: me.email ?? '' })
    setNotif({
      notify_telegram:  me.notify_telegram  ?? false,
      telegram_chat_id: me.telegram_chat_id ?? '',
      notify_whatsapp:  me.notify_whatsapp  ?? false,
      whatsapp_phone:   me.whatsapp_phone   ?? '',
      whatsapp_api_key: me.whatsapp_api_key ?? '',
      notify_email:     me.notify_email     ?? true,
    })
  }, [me])

  // ── Mutation: actualizar info personal ──
  const saveInfo = useMutation({
    mutationFn: () => authApi.updateMe({ full_name: info.full_name }),
    onSuccess: (updated) => {
      toast.success('Perfil actualizado')
      setUser(updated)
      qc.invalidateQueries({ queryKey: ['me'] })
    },
    onError: () => toast.error('Error al guardar'),
  })

  // ── Mutation: actualizar notificaciones ──
  const saveNotif = useMutation({
    mutationFn: () => authApi.updateMe(notif),
    onSuccess: () => {
      toast.success('Configuración de notificaciones guardada')
      qc.invalidateQueries({ queryKey: ['me'] })
    },
    onError: () => toast.error('Error al guardar'),
  })

  // ── Mutation: cambiar contraseña ──
  const changePwd = useMutation({
    mutationFn: () => authApi.changePassword(pwd.current, pwd.next),
    onSuccess: () => {
      toast.success('Contraseña actualizada')
      setPwd({ current: '', next: '', confirm: '' })
    },
    onError: (err) => {
      const msg = err?.response?.data?.detail ?? 'Error al cambiar contraseña'
      toast.error(msg)
    },
  })

  const pwdValid = pwd.current && pwd.next && pwd.next === pwd.confirm && pwd.next.length >= 8

  if (isLoading) return <div className="text-center text-gray-400 py-20">Cargando...</div>

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Mi perfil</h1>
        <p className="text-gray-500 text-sm mt-0.5">Configuración personal y notificaciones</p>
      </div>

      {/* ── Información personal ── */}
      <section className="card space-y-4">
        <div className="flex items-center gap-2 mb-2">
          <div className="bg-primary-100 rounded-lg p-2">
            <User className="w-4 h-4 text-primary-600" />
          </div>
          <h2 className="font-semibold text-gray-800">Información personal</h2>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className="label">Nombre de usuario</label>
            <input className="input bg-gray-50 cursor-not-allowed" value={me?.username ?? ''} readOnly />
          </div>
          <div>
            <label className="label">Email</label>
            <input className="input bg-gray-50 cursor-not-allowed" value={me?.email ?? ''} readOnly />
          </div>
          <div>
            <label className="label">Nombre completo</label>
            <input className="input" placeholder="Tu nombre"
              value={info.full_name}
              onChange={e => setInfo(f => ({ ...f, full_name: e.target.value }))} />
          </div>
          <div>
            <label className="label">Rol</label>
            <input className="input bg-gray-50 cursor-not-allowed capitalize" value={me?.role ?? ''} readOnly />
          </div>
        </div>

        <button
          onClick={() => saveInfo.mutate()}
          disabled={saveInfo.isPending || !info.full_name}
          className="btn-primary text-sm">
          {saveInfo.isPending ? 'Guardando...' : 'Guardar cambios'}
        </button>
      </section>

      {/* ── Notificaciones ── */}
      <section className="card space-y-5">
        <div className="flex items-center gap-2 mb-1">
          <div className="bg-yellow-50 rounded-lg p-2">
            <Bell className="w-4 h-4 text-yellow-600" />
          </div>
          <div>
            <h2 className="font-semibold text-gray-800">Canales de notificación</h2>
            <p className="text-xs text-gray-400">Las alertas críticas y altas llegarán por todos los canales activos</p>
          </div>
        </div>

        {/* Telegram */}
        <div className="border border-gray-100 rounded-xl p-4 space-y-3">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-800">Telegram</p>
              <p className="text-xs text-gray-400">Gratis · Sin límites prácticos · Alertas medium+</p>
            </div>
            <label className="flex items-center gap-2 cursor-pointer">
              <span className="text-xs text-gray-500">{notif.notify_telegram ? 'Activo' : 'Inactivo'}</span>
              <div
                onClick={() => setNotif(f => ({ ...f, notify_telegram: !f.notify_telegram }))}
                className={`relative w-10 h-5 rounded-full transition-colors cursor-pointer ${
                  notif.notify_telegram ? 'bg-primary-600' : 'bg-gray-300'
                }`}
              >
                <span className={`absolute top-0.5 w-4 h-4 rounded-full bg-white shadow transition-transform ${
                  notif.notify_telegram ? 'translate-x-5' : 'translate-x-0.5'
                }`} />
              </div>
            </label>
          </div>
          {notif.notify_telegram && (
            <div>
              <label className="label">Chat ID de Telegram</label>
              <input className="input" placeholder="Ej: 123456789"
                value={notif.telegram_chat_id}
                onChange={e => setNotif(f => ({ ...f, telegram_chat_id: e.target.value }))} />
              <p className="text-xs text-gray-400 mt-1">
                Envía <code className="bg-gray-100 px-1 rounded">/start</code> al bot y copia tu Chat ID.
              </p>
            </div>
          )}
        </div>

        {/* WhatsApp */}
        <div className="border border-gray-100 rounded-xl p-4 space-y-3">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-800">WhatsApp</p>
              <p className="text-xs text-gray-400">Via CallMeBot · Gratis · Alertas high/critical</p>
            </div>
            <label className="flex items-center gap-2 cursor-pointer">
              <span className="text-xs text-gray-500">{notif.notify_whatsapp ? 'Activo' : 'Inactivo'}</span>
              <div
                onClick={() => setNotif(f => ({ ...f, notify_whatsapp: !f.notify_whatsapp }))}
                className={`relative w-10 h-5 rounded-full transition-colors cursor-pointer ${
                  notif.notify_whatsapp ? 'bg-primary-600' : 'bg-gray-300'
                }`}
              >
                <span className={`absolute top-0.5 w-4 h-4 rounded-full bg-white shadow transition-transform ${
                  notif.notify_whatsapp ? 'translate-x-5' : 'translate-x-0.5'
                }`} />
              </div>
            </label>
          </div>
          {notif.notify_whatsapp && (
            <div className="space-y-3">
              <div>
                <label className="label">Teléfono (con código de país, sin +)</label>
                <input className="input" placeholder="Ej: 573001234567"
                  value={notif.whatsapp_phone}
                  onChange={e => setNotif(f => ({ ...f, whatsapp_phone: e.target.value }))} />
              </div>
              <div>
                <label className="label">API Key de CallMeBot</label>
                <input className="input" placeholder="Ej: 1234567"
                  value={notif.whatsapp_api_key}
                  onChange={e => setNotif(f => ({ ...f, whatsapp_api_key: e.target.value }))} />
                <p className="text-xs text-gray-400 mt-1">
                  Agrega <span className="font-medium">+34 644 62 08 61</span> a WhatsApp y envíale
                  &quot;I allow callmebot to send me messages&quot; para obtener tu API key.
                </p>
              </div>
            </div>
          )}
        </div>

        {/* Email */}
        <div className="border border-gray-100 rounded-xl p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-800">Email</p>
              <p className="text-xs text-gray-400">Gmail SMTP · Alertas high/critical · {me?.email}</p>
            </div>
            <div
              onClick={() => setNotif(f => ({ ...f, notify_email: !f.notify_email }))}
              className={`relative w-10 h-5 rounded-full transition-colors cursor-pointer ${
                notif.notify_email ? 'bg-primary-600' : 'bg-gray-300'
              }`}
            >
              <span className={`absolute top-0.5 w-4 h-4 rounded-full bg-white shadow transition-transform ${
                notif.notify_email ? 'translate-x-5' : 'translate-x-0.5'
              }`} />
            </div>
          </div>
        </div>

        <button
          onClick={() => saveNotif.mutate()}
          disabled={saveNotif.isPending}
          className="btn-primary text-sm">
          <CheckCircle2 className="w-4 h-4" />
          {saveNotif.isPending ? 'Guardando...' : 'Guardar notificaciones'}
        </button>
      </section>

      {/* ── Cambiar contraseña ── */}
      <section className="card space-y-4">
        <div className="flex items-center gap-2 mb-1">
          <div className="bg-gray-100 rounded-lg p-2">
            <Lock className="w-4 h-4 text-gray-600" />
          </div>
          <h2 className="font-semibold text-gray-800">Cambiar contraseña</h2>
        </div>

        <div>
          <label className="label">Contraseña actual</label>
          <div className="relative">
            <input
              type={showPwd ? 'text' : 'password'}
              className="input pr-10"
              placeholder="Contraseña actual"
              value={pwd.current}
              onChange={e => setPwd(f => ({ ...f, current: e.target.value }))} />
            <button type="button"
              onClick={() => setShowPwd(v => !v)}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400">
              {showPwd ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
            </button>
          </div>
        </div>

        <div>
          <label className="label">Nueva contraseña</label>
          <input
            type={showPwd ? 'text' : 'password'}
            className="input"
            placeholder="Mínimo 8 caracteres"
            value={pwd.next}
            onChange={e => setPwd(f => ({ ...f, next: e.target.value }))} />
        </div>

        <div>
          <label className="label">Confirmar nueva contraseña</label>
          <input
            type={showPwd ? 'text' : 'password'}
            className={`input ${pwd.confirm && pwd.confirm !== pwd.next ? 'border-red-400' : ''}`}
            placeholder="Repetir contraseña"
            value={pwd.confirm}
            onChange={e => setPwd(f => ({ ...f, confirm: e.target.value }))} />
          {pwd.confirm && pwd.confirm !== pwd.next && (
            <p className="text-xs text-red-500 mt-1">Las contraseñas no coinciden</p>
          )}
        </div>

        <button
          onClick={() => changePwd.mutate()}
          disabled={changePwd.isPending || !pwdValid}
          className="btn-primary text-sm">
          <Lock className="w-4 h-4" />
          {changePwd.isPending ? 'Actualizando...' : 'Cambiar contraseña'}
        </button>
      </section>
    </div>
  )
}
