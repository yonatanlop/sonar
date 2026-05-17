import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import {
  RefreshCw, CheckCircle, AlertTriangle, XCircle, Users, Clock,
  BarChart2, Info, ChevronDown, ChevronUp, Plus, Trash2, Zap, Pencil,
} from 'lucide-react'
import { formatDistanceToNow } from 'date-fns'
import { es } from 'date-fns/locale'
import client from '../api/client'
import { useAuthStore } from '../store/authStore'

const fetchStatus     = () => client.get('/platforms/status').then(r => r.data)
const fetchTwAccounts = () => client.get('/platforms/twitter/accounts').then(r => r.data)
const addTwAccount    = (body) => client.post('/platforms/twitter/accounts', body).then(r => r.data)
const updateTwAccount = ({ username, ...body }) => client.put(`/platforms/twitter/accounts/${username}`, body).then(r => r.data)
const activateTwAcc   = (username) => client.post(`/platforms/twitter/accounts/${username}/activate`).then(r => r.data)
const deleteTwAcc     = (username) => client.delete(`/platforms/twitter/accounts/${username}`).then(r => r.data)

const fetchIgAccounts = () => client.get('/platforms/instagram/accounts').then(r => r.data)
const addIgAccount    = (body) => client.post('/platforms/instagram/accounts', body).then(r => r.data)
const toggleIgAcc     = (username) => client.post(`/platforms/instagram/accounts/${username}/toggle`).then(r => r.data)
const deleteIgAcc     = (username) => client.delete(`/platforms/instagram/accounts/${username}`).then(r => r.data)

const saveFbCookies   = (body) => client.post('/platforms/facebook/cookies', body).then(r => r.data)
const deleteFbCookies = () => client.delete('/platforms/facebook/cookies').then(r => r.data)

const daysSince = (isoStr) => Math.floor((Date.now() - new Date(isoStr)) / 86_400_000)

// ── Subcomponentes ─────────────────────────────────────────────────────────

function StatusBadge({ status }) {
  if (status === 'ok') return (
    <span className="inline-flex items-center gap-1.5 text-xs font-semibold text-green-700 bg-green-50 border border-green-200 rounded-full px-2.5 py-1">
      <CheckCircle className="w-3.5 h-3.5" /> Activa
    </span>
  )
  if (status === 'warning') return (
    <span className="inline-flex items-center gap-1.5 text-xs font-semibold text-yellow-700 bg-yellow-50 border border-yellow-200 rounded-full px-2.5 py-1">
      <AlertTriangle className="w-3.5 h-3.5" /> Sin menciones recientes
    </span>
  )
  return (
    <span className="inline-flex items-center gap-1.5 text-xs font-semibold text-red-700 bg-red-50 border border-red-200 rounded-full px-2.5 py-1">
      <XCircle className="w-3.5 h-3.5" /> No configurada
    </span>
  )
}

function StatBox({ label, value }) {
  return (
    <div className="text-center">
      <p className="text-2xl font-bold text-gray-800">{value ?? '—'}</p>
      <p className="text-xs text-gray-500 mt-0.5">{label}</p>
    </div>
  )
}

// ── Panel de gestión de cuentas Twitter ────────────────────────────────────

const EMPTY_FORM = { username: '', email: '', password: '', email_password: '', cookies_json: '' }
const EMPTY_EDIT = { cookies_json: '', password: '' }

function TwitterAccountsPanel() {
  const qc = useQueryClient()
  const [open, setOpen]         = useState(false)
  const [showAdd, setShowAdd]   = useState(false)
  const [editingAcc, setEditingAcc] = useState(null)   // username being edited
  const [addMode, setAddMode]   = useState('cookies')
  const [addForm, setAddForm]   = useState(EMPTY_FORM)
  const [editForm, setEditForm] = useState(EMPTY_EDIT)
  const [error, setError]       = useState('')

  const { data: accounts = [], isLoading } = useQuery({
    queryKey: ['tw-accounts'],
    queryFn:  fetchTwAccounts,
    enabled:  open,
  })

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ['tw-accounts'] })
    qc.invalidateQueries({ queryKey: ['platforms-status'] })
  }

  const addMut = useMutation({
    mutationFn: addTwAccount,
    onSuccess: () => { setShowAdd(false); setAddForm(EMPTY_FORM); setError(''); invalidate() },
    onError: (e) => setError(e.response?.data?.detail || 'Error al agregar la cuenta'),
  })

  const updateMut = useMutation({
    mutationFn: updateTwAccount,
    onSuccess: () => { setEditingAcc(null); setEditForm(EMPTY_EDIT); setError(''); invalidate() },
    onError: (e) => setError(e.response?.data?.detail || 'Error al actualizar la cuenta'),
  })

  const activateMut = useMutation({ mutationFn: activateTwAcc, onSuccess: invalidate })
  const deleteMut   = useMutation({ mutationFn: deleteTwAcc,   onSuccess: invalidate })

  const handleAdd = (e) => {
    e.preventDefault()
    setError('')
    if (!addForm.username || !addForm.email || !addForm.password) {
      setError('Usuario, email y contraseña son obligatorios.')
      return
    }
    if (addMode === 'cookies' && !addForm.cookies_json.trim()) {
      setError('Pega el JSON de cookies exportado desde Cookie-Editor.')
      return
    }
    addMut.mutate({
      username:       addForm.username,
      email:          addForm.email,
      password:       addForm.password,
      email_password: addForm.email_password || addForm.password,
      cookies_json:   addMode === 'cookies' ? addForm.cookies_json : '',
    })
  }

  const handleEdit = (e) => {
    e.preventDefault()
    setError('')
    if (!editForm.cookies_json.trim() && !editForm.password.trim()) {
      setError('Ingresa nuevas cookies o una nueva contraseña.')
      return
    }
    updateMut.mutate({ username: editingAcc, ...editForm })
  }

  const startEdit = (acc) => {
    setEditingAcc(acc.username)
    setEditForm(EMPTY_EDIT)
    setShowAdd(false)
    setError('')
  }

  return (
    <div className="border-t border-gray-100 mt-3 pt-3">
      <button
        onClick={() => setOpen(v => !v)}
        className="flex items-center gap-2 text-xs text-gray-500 hover:text-gray-700 transition-colors w-full"
      >
        <Users className="w-3.5 h-3.5" />
        <span className="flex-1 text-left">Gestionar cuentas</span>
        {open ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
      </button>

      {open && (
        <div className="mt-3 space-y-3">
          {isLoading && <p className="text-xs text-gray-400">Cargando...</p>}

          {!isLoading && accounts.length === 0 && (
            <p className="text-xs text-gray-400 text-center py-2">No hay cuentas en el pool.</p>
          )}

          {accounts.map(acc => (
            <div key={acc.username} className="space-y-2">
              {/* Fila de cuenta */}
              <div className="flex items-center gap-2 bg-gray-50 rounded-lg px-3 py-2 text-xs min-w-0">
                <span className={`w-2 h-2 rounded-full shrink-0 ${acc.active ? 'bg-green-500' : 'bg-red-400'}`} />
                <div className="flex-1 min-w-0">
                  <p className="font-medium text-gray-700 truncate">@{acc.username}</p>
                  <p className="text-gray-400 truncate">{acc.email}</p>
                </div>
                {acc.has_cookies && <span title="Tiene cookies" className="shrink-0">🍪</span>}

                {/* Botones siempre visibles */}
                <div className="flex items-center gap-1 shrink-0">
                  {!acc.active && (
                    <button onClick={() => activateMut.mutate(acc.username)}
                      disabled={activateMut.isPending}
                      title="Activar cuenta"
                      className="p-1 rounded text-green-600 hover:bg-green-50 transition-colors">
                      <Zap className="w-3.5 h-3.5" />
                    </button>
                  )}
                  <button
                    onClick={() => editingAcc === acc.username ? setEditingAcc(null) : startEdit(acc)}
                    title="Editar cookies / contraseña"
                    className={`p-1 rounded transition-colors ${editingAcc === acc.username ? 'text-primary-600 bg-primary-50' : 'text-gray-400 hover:text-primary-600 hover:bg-primary-50'}`}>
                    <Pencil className="w-3.5 h-3.5" />
                  </button>
                  <button
                    onClick={() => { if (window.confirm(`¿Eliminar @${acc.username} del pool?`)) deleteMut.mutate(acc.username) }}
                    disabled={deleteMut.isPending}
                    title="Eliminar cuenta"
                    className="p-1 rounded text-red-400 hover:text-red-600 hover:bg-red-50 transition-colors">
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>

              {/* Formulario de edición inline */}
              {editingAcc === acc.username && (
                <form onSubmit={handleEdit}
                  className="space-y-2 bg-blue-50 rounded-lg p-3 border border-blue-100">
                  <p className="text-xs font-semibold text-blue-800">
                    Actualizar @{acc.username}
                  </p>
                  <p className="text-xs text-blue-600">
                    Renueva las cookies para solucionar errores de autenticación.
                    Deja en blanco lo que no quieras cambiar.
                  </p>

                  <div>
                    <textarea
                      className="input text-xs w-full font-mono resize-none"
                      rows={4}
                      placeholder={'Nuevas cookies JSON\n(Cookie-Editor → Export as JSON)'}
                      value={editForm.cookies_json}
                      onChange={e => setEditForm(f => ({...f, cookies_json: e.target.value}))}
                    />
                    <p className="text-xs text-gray-400 mt-0.5">
                      Chrome/Edge → twitter.com → Cookie-Editor → Export as JSON
                    </p>
                  </div>

                  <input className="input text-xs w-full" placeholder="Nueva contraseña (opcional)"
                    type="password"
                    value={editForm.password}
                    onChange={e => setEditForm(f => ({...f, password: e.target.value}))} />

                  {error && <p className="text-xs text-red-600">{error}</p>}

                  <div className="flex gap-2 pt-1">
                    <button type="submit" disabled={updateMut.isPending}
                      className="btn-primary text-xs py-1.5 flex-1">
                      {updateMut.isPending ? 'Guardando...' : 'Guardar cambios'}
                    </button>
                    <button type="button"
                      onClick={() => { setEditingAcc(null); setError('') }}
                      className="btn-secondary text-xs py-1.5 flex-1">
                      Cancelar
                    </button>
                  </div>
                </form>
              )}
            </div>
          ))}

          {/* Botón agregar */}
          {!showAdd && !editingAcc && (
            <button onClick={() => setShowAdd(true)}
              className="flex items-center gap-1.5 text-xs text-primary-600 hover:text-primary-800 transition-colors">
              <Plus className="w-3.5 h-3.5" /> Agregar cuenta
            </button>
          )}

          {/* Formulario agregar */}
          {showAdd && (
            <form onSubmit={handleAdd} className="space-y-2 bg-gray-50 rounded-lg p-3 border border-gray-200">
              <p className="text-xs font-semibold text-gray-700">Nueva cuenta Twitter/X</p>

              <div className="flex gap-2">
                {['cookies','password'].map(m => (
                  <button key={m} type="button" onClick={() => setAddMode(m)}
                    className={`flex-1 text-xs py-1 rounded-md border transition-colors ${
                      addMode === m
                        ? 'bg-primary-600 text-white border-primary-600'
                        : 'bg-white text-gray-600 border-gray-200 hover:border-primary-400'
                    }`}>
                    {m === 'cookies' ? '🍪 Cookies (recomendado)' : '🔑 Usuario/Contraseña'}
                  </button>
                ))}
              </div>

              <input className="input text-xs w-full" placeholder="Usuario (sin @)"
                value={addForm.username} onChange={e => setAddForm(f => ({...f, username: e.target.value}))} />
              <input className="input text-xs w-full" placeholder="Email" type="email"
                value={addForm.email} onChange={e => setAddForm(f => ({...f, email: e.target.value}))} />
              <input className="input text-xs w-full" placeholder="Contraseña de Twitter" type="password"
                value={addForm.password} onChange={e => setAddForm(f => ({...f, password: e.target.value}))} />

              {addMode === 'password' && (
                <input className="input text-xs w-full" placeholder="Contraseña del email (si es distinta)" type="password"
                  value={addForm.email_password} onChange={e => setAddForm(f => ({...f, email_password: e.target.value}))} />
              )}

              {addMode === 'cookies' && (
                <div>
                  <textarea className="input text-xs w-full font-mono resize-none" rows={4}
                    placeholder={'Pega aquí el JSON de cookies\n(Cookie-Editor → Export as JSON)'}
                    value={addForm.cookies_json}
                    onChange={e => setAddForm(f => ({...f, cookies_json: e.target.value}))} />
                  <p className="text-xs text-gray-400 mt-1">
                    Instala <strong>Cookie-Editor</strong> en Chrome/Edge → entra a twitter.com → Export as JSON
                  </p>
                </div>
              )}

              {error && <p className="text-xs text-red-600">{error}</p>}

              <div className="flex gap-2 pt-1">
                <button type="submit" disabled={addMut.isPending}
                  className="btn-primary text-xs py-1.5 flex-1">
                  {addMut.isPending ? 'Agregando...' : 'Agregar'}
                </button>
                <button type="button" onClick={() => { setShowAdd(false); setError('') }}
                  className="btn-secondary text-xs py-1.5 flex-1">
                  Cancelar
                </button>
              </div>
            </form>
          )}
        </div>
      )}
    </div>
  )
}

// ── Panel de gestión de cuentas Instagram ─────────────────────────────────

function InstagramAccountsPanel() {
  const qc = useQueryClient()
  const [open, setOpen]     = useState(false)
  const [showAdd, setShowAdd] = useState(false)
  const [form, setForm]     = useState({ username: '', password: '' })
  const [error, setError]   = useState('')

  const { data: accounts = [], isLoading } = useQuery({
    queryKey: ['ig-accounts'],
    queryFn:  fetchIgAccounts,
    enabled:  open,
  })

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ['ig-accounts'] })
    qc.invalidateQueries({ queryKey: ['platforms-status'] })
  }

  const addMut    = useMutation({ mutationFn: addIgAccount,  onSuccess: () => { setShowAdd(false); setForm({ username: '', password: '' }); setError(''); invalidate() }, onError: (e) => setError(e.response?.data?.detail || 'Error al agregar') })
  const toggleMut = useMutation({ mutationFn: toggleIgAcc,   onSuccess: invalidate })
  const deleteMut = useMutation({ mutationFn: deleteIgAcc,   onSuccess: invalidate })

  const handleAdd = (e) => {
    e.preventDefault()
    if (!form.username || !form.password) { setError('Usuario y contraseña son obligatorios.'); return }
    addMut.mutate(form)
  }

  return (
    <div className="border-t border-gray-100 mt-3 pt-3">
      <button onClick={() => setOpen(v => !v)}
        className="flex items-center gap-2 text-xs text-gray-500 hover:text-gray-700 transition-colors w-full">
        <Users className="w-3.5 h-3.5" />
        <span className="flex-1 text-left">Gestionar cuentas</span>
        {open ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
      </button>

      {open && (
        <div className="mt-3 space-y-3">
          {isLoading && <p className="text-xs text-gray-400">Cargando...</p>}
          {!isLoading && accounts.length === 0 && (
            <p className="text-xs text-gray-400 text-center py-2">No hay cuentas configuradas.</p>
          )}

          {accounts.map(acc => (
            <div key={acc.username} className="flex items-center gap-2 bg-gray-50 rounded-lg px-3 py-2 text-xs">
              <span className={`w-2 h-2 rounded-full shrink-0 ${acc.active ? 'bg-green-500' : 'bg-red-400'}`} />
              <p className="flex-1 font-medium text-gray-700 truncate">@{acc.username}</p>
              <button onClick={() => toggleMut.mutate(acc.username)} disabled={toggleMut.isPending}
                className={`px-2 py-0.5 rounded border text-xs transition-colors ${acc.active ? 'border-yellow-200 text-yellow-700 hover:bg-yellow-50' : 'border-green-200 text-green-700 hover:bg-green-50'}`}>
                {acc.active ? 'Desactivar' : 'Activar'}
              </button>
              <button onClick={() => { if (window.confirm(`¿Eliminar @${acc.username}?`)) deleteMut.mutate(acc.username) }}
                disabled={deleteMut.isPending}
                className="p-1 rounded text-red-400 hover:text-red-600 hover:bg-red-50 transition-colors">
                <Trash2 className="w-3.5 h-3.5" />
              </button>
            </div>
          ))}

          {!showAdd && (
            <button onClick={() => setShowAdd(true)}
              className="flex items-center gap-1.5 text-xs text-primary-600 hover:text-primary-800 transition-colors">
              <Plus className="w-3.5 h-3.5" /> Agregar cuenta
            </button>
          )}

          {showAdd && (
            <form onSubmit={handleAdd} className="space-y-2 bg-gray-50 rounded-lg p-3 border border-gray-200">
              <p className="text-xs font-semibold text-gray-700">Nueva cuenta Instagram</p>
              <input className="input text-xs w-full" placeholder="Usuario (sin @)"
                value={form.username} onChange={e => setForm(f => ({ ...f, username: e.target.value }))} />
              <input className="input text-xs w-full" placeholder="Contraseña" type="password"
                value={form.password} onChange={e => setForm(f => ({ ...f, password: e.target.value }))} />
              {error && <p className="text-xs text-red-600">{error}</p>}
              <div className="flex gap-2 pt-1">
                <button type="submit" disabled={addMut.isPending} className="btn-primary text-xs py-1.5 flex-1">
                  {addMut.isPending ? 'Agregando...' : 'Agregar'}
                </button>
                <button type="button" onClick={() => { setShowAdd(false); setError('') }} className="btn-secondary text-xs py-1.5 flex-1">Cancelar</button>
              </div>
            </form>
          )}
        </div>
      )}
    </div>
  )
}

// ── Panel de cookies Facebook ──────────────────────────────────────────────

function FacebookCookiesPanel({ configured, updatedAt }) {
  const qc = useQueryClient()
  const [open, setOpen]           = useState(false)
  const [cookies, setCookies]     = useState('')
  const [error, setError]         = useState('')
  const [testResult, setTestResult] = useState(null)

  const invalidate = () => qc.invalidateQueries({ queryKey: ['platforms-status'] })

  const saveMut   = useMutation({
    mutationFn: saveFbCookies,
    onSuccess: () => { setCookies(''); setError(''); setOpen(false); setTestResult(null); invalidate() },
    onError: (e) => setError(e.response?.data?.detail || 'Error al guardar cookies'),
  })
  const deleteMut = useMutation({ mutationFn: deleteFbCookies, onSuccess: () => { setTestResult(null); invalidate() } })

  const testMut = useMutation({
    mutationFn: () => client.post('/platforms/facebook/test').then(r => r.data),
    onSuccess: (data) => setTestResult(data),
    onError:   (e)    => setTestResult({ ok: false, message: e.response?.data?.detail ?? 'Error al probar' }),
  })
  const triggerMut = useMutation({
    mutationFn: () => client.post('/platforms/facebook/trigger').then(r => r.data),
    onSuccess:  () => toast.success('Scraping iniciado — los resultados aparecerán en ~1 minuto'),
    onError:    (e) => toast.error(e.response?.data?.detail ?? 'Error al iniciar scraping'),
  })

  const handleSave = (e) => {
    e.preventDefault()
    if (!cookies.trim()) { setError('Pega el JSON de cookies.'); return }
    saveMut.mutate({ cookies_json: cookies })
  }

  return (
    <div className="border-t border-gray-100 mt-3 pt-3">
      <button onClick={() => setOpen(v => !v)}
        className="flex items-center gap-2 text-xs text-gray-500 hover:text-gray-700 transition-colors w-full">
        <Users className="w-3.5 h-3.5" />
        <span className="flex-1 text-left">Gestionar cookies</span>
        {open ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
      </button>

      {open && (
        <div className="mt-3 space-y-3">
          {configured && (
            <div className="space-y-2">
              <div className="flex items-center justify-between bg-green-50 rounded-lg px-3 py-2 text-xs">
                <span className="text-green-700 font-medium">✓ Cookies configuradas</span>
                {updatedAt && <span className="text-gray-400">{formatDistanceToNow(new Date(updatedAt), { addSuffix: true, locale: es })}</span>}
                <button onClick={() => { if (window.confirm('¿Eliminar las cookies de Facebook?')) deleteMut.mutate() }}
                  disabled={deleteMut.isPending}
                  className="p-1 rounded text-red-400 hover:text-red-600 hover:bg-red-50">
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              </div>

              {updatedAt && daysSince(updatedAt) > 30 && (
                <div className="flex items-center gap-1.5 text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2">
                  <AlertTriangle className="w-3.5 h-3.5 shrink-0" />
                  Las cookies tienen {daysSince(updatedAt)} días — pueden haber expirado
                </div>
              )}

              {testResult && (
                <div className={`flex items-start gap-2 text-xs rounded-lg px-3 py-2 ${
                  testResult.ok ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-700'
                }`}>
                  {testResult.ok
                    ? <CheckCircle className="w-3.5 h-3.5 shrink-0 mt-0.5" />
                    : <XCircle className="w-3.5 h-3.5 shrink-0 mt-0.5" />}
                  <span>
                    {testResult.message}
                    {!testResult.ok && testResult.error && (
                      <code className="block mt-0.5 text-[10px] opacity-70 break-all">{testResult.error.slice(0, 120)}</code>
                    )}
                  </span>
                </div>
              )}

              <div className="flex gap-2">
                <button onClick={() => testMut.mutate()} disabled={testMut.isPending}
                  className="btn-secondary text-xs py-1.5 flex-1">
                  {testMut.isPending ? 'Probando…' : '🔌 Probar conexión'}
                </button>
                <button onClick={() => triggerMut.mutate()} disabled={triggerMut.isPending}
                  className="btn-secondary text-xs py-1.5 flex-1">
                  {triggerMut.isPending ? 'Enviando…' : '▶ Ejecutar ahora'}
                </button>
              </div>
            </div>
          )}

          <form onSubmit={handleSave} className="space-y-2">
            <textarea className="input text-xs w-full font-mono resize-none" rows={4}
              placeholder={'Pega aquí el JSON de cookies\n(Cookie-Editor → Export as JSON desde facebook.com)'}
              value={cookies} onChange={e => setCookies(e.target.value)} />
            {error && <p className="text-xs text-red-600">{error}</p>}
            <div className="flex gap-2">
              <button type="submit" disabled={saveMut.isPending} className="btn-primary text-xs py-1.5 flex-1">
                {saveMut.isPending ? 'Guardando...' : configured ? 'Actualizar cookies' : 'Guardar cookies'}
              </button>
              <button type="button" onClick={() => { setOpen(false); setError('') }} className="btn-secondary text-xs py-1.5 flex-1">Cancelar</button>
            </div>
          </form>
        </div>
      )}
    </div>
  )
}

// ── Tarjeta de plataforma ──────────────────────────────────────────────────

function PlatformCard({ platform, isAdmin }) {
  const borderColor =
    platform.status === 'ok'      ? 'border-green-200'  :
    platform.status === 'warning' ? 'border-yellow-200' : 'border-red-200'

  const topBar =
    platform.status === 'ok'      ? 'bg-green-500'  :
    platform.status === 'warning' ? 'bg-yellow-400' : 'bg-red-400'

  const lastSeen = platform.last_mention_at
    ? formatDistanceToNow(new Date(platform.last_mention_at), { addSuffix: true, locale: es })
    : null

  return (
    <div className={`bg-white rounded-xl border-2 ${borderColor} shadow-sm overflow-hidden flex flex-col`}>
      <div className={`h-1.5 w-full ${topBar}`} />

      <div className="p-5 flex flex-col gap-4 flex-1">
        {/* Header */}
        <div className="flex items-start justify-between gap-2">
          <div className="flex items-center gap-3">
            <span className="text-3xl">{platform.icon}</span>
            <div>
              <h2 className="font-bold text-gray-900 text-base leading-tight">{platform.name}</h2>
              <p className="text-xs text-gray-400 flex items-center gap-1 mt-0.5">
                <Clock className="w-3 h-3" /> {platform.frequency}
              </p>
            </div>
          </div>
          <StatusBadge status={platform.status} />
        </div>

        {/* Stats */}
        <div className="grid grid-cols-3 gap-2 bg-gray-50 rounded-lg p-3">
          <StatBox label="Últ. 24 h" value={platform.mentions_24h} />
          <StatBox label="Últ. 7 días" value={platform.mentions_7d} />
          <div className="text-center">
            <p className="text-xs text-gray-800 font-medium leading-tight">
              {lastSeen ?? 'Sin datos'}
            </p>
            <p className="text-xs text-gray-500 mt-0.5">Última mención</p>
          </div>
        </div>

        {/* Twitter tiers status */}
        {platform.code === 'twitter' && (
          <div className="space-y-1.5">
            <div className="flex items-center gap-2 text-sm text-gray-600 bg-gray-50 rounded-lg px-3 py-2">
              <Users className="w-4 h-4 shrink-0 text-gray-400" />
              <span className="flex-1">
                <strong>{platform.accounts_active}</strong> cuenta{platform.accounts_active !== 1 ? 's' : ''} activa{platform.accounts_active !== 1 ? 's' : ''} (Tier 1)
                {platform.accounts_total > 0 && platform.accounts_total !== platform.accounts_active &&
                  <span className="text-gray-400"> / {platform.accounts_total} total</span>
                }
              </span>
            </div>
            <div className={`flex items-center gap-2 text-sm rounded-lg px-3 py-2 ${
              platform.bearer_configured
                ? 'bg-green-50 text-green-700'
                : 'bg-gray-50 text-gray-500'
            }`}>
              <Zap className={`w-4 h-4 shrink-0 ${platform.bearer_configured ? 'text-green-500' : 'text-gray-400'}`} />
              <span>
                API v2 Bearer Token (Tier 2):{' '}
                <strong>{platform.bearer_configured ? 'configurado ✓' : 'no configurado'}</strong>
              </span>
            </div>
          </div>
        )}

        {/* Instagram accounts count */}
        {platform.code === 'instagram' && (
          <div className="flex items-center gap-2 text-sm text-gray-600 bg-gray-50 rounded-lg px-3 py-2">
            <Users className="w-4 h-4 shrink-0 text-gray-400" />
            <span className="flex-1">
              <strong>{platform.accounts_active ?? 0}</strong> cuenta{platform.accounts_active !== 1 ? 's' : ''} activa{platform.accounts_active !== 1 ? 's' : ''}
              {platform.accounts_total > 0 && platform.accounts_total !== platform.accounts_active &&
                <span className="text-gray-400"> / {platform.accounts_total} total</span>
              }
            </span>
          </div>
        )}

        {/* Needs action */}
        {platform.needs_action && (
          <div className="flex items-start gap-2 bg-red-50 border border-red-100 rounded-lg px-3 py-2.5 text-xs text-red-700">
            <XCircle className="w-4 h-4 shrink-0 mt-0.5 text-red-500" />
            <p>{platform.needs_action}</p>
          </div>
        )}

        {/* Setup hint */}
        <div className="flex items-start gap-2 bg-blue-50 border border-blue-100 rounded-lg px-3 py-2.5 text-xs text-blue-700 mt-auto">
          <Info className="w-4 h-4 shrink-0 mt-0.5 text-blue-400" />
          <p>{platform.setup_hint}</p>
        </div>

        {/* Twitter account manager (admin only) */}
        {platform.code === 'twitter' && isAdmin && <TwitterAccountsPanel />}

        {/* Instagram account manager (admin only) */}
        {platform.code === 'instagram' && isAdmin && <InstagramAccountsPanel />}

        {/* Facebook cookies manager (admin only) */}
        {platform.code === 'facebook' && isAdmin && (
          <FacebookCookiesPanel configured={platform.configured} updatedAt={platform.cookies_updated_at} />
        )}
      </div>
    </div>
  )
}

// ── Página principal ───────────────────────────────────────────────────────

export default function Platforms() {
  const isAdmin = useAuthStore(s => s.isAdmin())

  const { data: platforms = [], isLoading, isError, refetch, isFetching } = useQuery({
    queryKey: ['platforms-status'],
    queryFn:  fetchStatus,
    refetchInterval: 60_000,
  })

  const ok      = platforms.filter(p => p.status === 'ok').length
  const warning = platforms.filter(p => p.status === 'warning').length
  const error   = platforms.filter(p => p.status === 'error').length

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <BarChart2 className="w-6 h-6 text-primary-500" />
            Estado de Plataformas
          </h1>
          <p className="text-gray-500 text-sm mt-0.5">
            Monitorea qué redes sociales están activas y recolectando menciones
          </p>
        </div>
        <button
          onClick={() => refetch()}
          disabled={isFetching}
          className="btn-secondary flex items-center gap-2 text-sm"
        >
          <RefreshCw className={`w-4 h-4 ${isFetching ? 'animate-spin' : ''}`} />
          Actualizar
        </button>
      </div>

      {/* Summary pills */}
      {!isLoading && !isError && (
        <div className="flex flex-wrap gap-3">
          <span className="inline-flex items-center gap-1.5 bg-green-50 border border-green-200 text-green-700 text-sm font-medium rounded-full px-3 py-1">
            <CheckCircle className="w-4 h-4" /> {ok} activa{ok !== 1 ? 's' : ''}
          </span>
          <span className="inline-flex items-center gap-1.5 bg-yellow-50 border border-yellow-200 text-yellow-700 text-sm font-medium rounded-full px-3 py-1">
            <AlertTriangle className="w-4 h-4" /> {warning} sin menciones recientes
          </span>
          <span className="inline-flex items-center gap-1.5 bg-red-50 border border-red-200 text-red-700 text-sm font-medium rounded-full px-3 py-1">
            <XCircle className="w-4 h-4" /> {error} no configurada{error !== 1 ? 's' : ''}
          </span>
        </div>
      )}

      {/* Loading skeleton */}
      {isLoading && (
        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="bg-white rounded-xl border-2 border-gray-100 h-64 animate-pulse" />
          ))}
        </div>
      )}

      {/* Error */}
      {isError && (
        <div className="card border-red-200 border bg-red-50 text-red-700 text-sm py-4 text-center">
          No se pudo cargar el estado de las plataformas. Verifica que el backend esté en línea.
        </div>
      )}

      {/* Cards */}
      {!isLoading && !isError && (
        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
          {platforms.map(p => <PlatformCard key={p.code} platform={p} isAdmin={isAdmin} />)}
        </div>
      )}

      <p className="text-xs text-gray-400 text-center">
        Se actualiza automáticamente cada 60 segundos
      </p>
    </div>
  )
}
