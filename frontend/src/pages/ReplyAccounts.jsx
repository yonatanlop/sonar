import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { MessageSquareReply, Plus, Pencil, Trash2, UserCheck, UserX, X, ChevronDown, ChevronUp, ExternalLink } from 'lucide-react'
import toast from 'react-hot-toast'
import client from '../api/client'

const fetchAccounts = () => client.get('/reply-accounts').then(r => r.data)
const fetchStats    = () => client.get('/reply-accounts/stats').then(r => r.data)
const fetchReplies  = (id) => client.get(`/reply-accounts/${id}/replies`).then(r => r.data)
const fetchPlatforms = () => client.get('/platforms').then(r => r.data)

const PLATFORM_ICON = { twitter: '🐦', reddit: '🤖', youtube: '▶️', instagram: '📸', facebook: '👥', rss: '📰' }

function fmtDate(dt) {
  if (!dt) return '—'
  return new Date(dt).toLocaleDateString('es', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' })
}

const EMPTY_ACCOUNT = { platform_id: '', username: '', display_name: '', description: '' }
const EMPTY_REPLY   = { content: '', replied_at: '', external_reply_url: '', mention_url: '' }

export default function ReplyAccounts() {
  const qc = useQueryClient()
  const [selected, setSelected]       = useState(null)
  const [showAccountModal, setShowAccountModal] = useState(false)
  const [editingAccount, setEditingAccount]     = useState(null)
  const [accountForm, setAccountForm]           = useState(EMPTY_ACCOUNT)
  const [showReplyModal, setShowReplyModal]     = useState(false)
  const [replyForm, setReplyForm]               = useState(EMPTY_REPLY)

  const { data: stats = {} }    = useQuery({ queryKey: ['reply-accounts-stats'],    queryFn: fetchStats })
  const { data: accounts = [], isLoading } = useQuery({ queryKey: ['reply-accounts'], queryFn: fetchAccounts })
  const { data: platforms = [] } = useQuery({ queryKey: ['platforms'],              queryFn: fetchPlatforms })
  const { data: replies = [], isLoading: loadingReplies } = useQuery({
    queryKey: ['reply-account-replies', selected],
    queryFn:  () => fetchReplies(selected),
    enabled:  !!selected,
  })

  const createAccount = useMutation({
    mutationFn: (body) => client.post('/reply-accounts', body),
    onSuccess: () => {
      toast.success('Cuenta creada')
      qc.invalidateQueries({ queryKey: ['reply-accounts'] })
      qc.invalidateQueries({ queryKey: ['reply-accounts-stats'] })
      setShowAccountModal(false)
      setAccountForm(EMPTY_ACCOUNT)
    },
    onError: () => toast.error('Error al crear cuenta'),
  })

  const updateAccount = useMutation({
    mutationFn: ({ id, body }) => client.put(`/reply-accounts/${id}`, body),
    onSuccess: () => {
      toast.success('Cuenta actualizada')
      qc.invalidateQueries({ queryKey: ['reply-accounts'] })
      qc.invalidateQueries({ queryKey: ['reply-accounts-stats'] })
      setEditingAccount(null)
      setShowAccountModal(false)
    },
    onError: () => toast.error('Error al actualizar cuenta'),
  })

  const deleteAccount = useMutation({
    mutationFn: (id) => client.delete(`/reply-accounts/${id}`),
    onSuccess: () => {
      toast.success('Cuenta eliminada')
      qc.invalidateQueries({ queryKey: ['reply-accounts'] })
      qc.invalidateQueries({ queryKey: ['reply-accounts-stats'] })
      if (selected && accounts.find(a => a.id === selected) === undefined) setSelected(null)
    },
    onError: () => toast.error('Error al eliminar cuenta'),
  })

  const toggleActive = useMutation({
    mutationFn: ({ id, active }) => client.put(`/reply-accounts/${id}`, { active: !active }),
    onSuccess: () => {
      toast.success('Estado actualizado')
      qc.invalidateQueries({ queryKey: ['reply-accounts'] })
      qc.invalidateQueries({ queryKey: ['reply-accounts-stats'] })
    },
  })

  const logReply = useMutation({
    mutationFn: (body) => client.post(`/reply-accounts/${selected}/replies`, body),
    onSuccess: () => {
      toast.success('Respuesta registrada')
      qc.invalidateQueries({ queryKey: ['reply-account-replies', selected] })
      qc.invalidateQueries({ queryKey: ['reply-accounts'] })
      qc.invalidateQueries({ queryKey: ['reply-accounts-stats'] })
      setShowReplyModal(false)
      setReplyForm(EMPTY_REPLY)
    },
    onError: () => toast.error('Error al registrar respuesta'),
  })

  function openCreate() {
    setEditingAccount(null)
    setAccountForm(EMPTY_ACCOUNT)
    setShowAccountModal(true)
  }

  function openEdit(account) {
    setEditingAccount(account)
    setAccountForm({
      platform_id: account.platform?.id ?? '',
      username: account.username,
      display_name: account.display_name ?? '',
      description: account.description ?? '',
    })
    setShowAccountModal(true)
  }

  function submitAccount() {
    const body = {
      ...accountForm,
      platform_id: Number(accountForm.platform_id),
    }
    if (editingAccount) {
      updateAccount.mutate({ id: editingAccount.id, body })
    } else {
      createAccount.mutate(body)
    }
  }

  function submitReply() {
    logReply.mutate({
      content: replyForm.content,
      replied_at: new Date(replyForm.replied_at).toISOString(),
      external_reply_url: replyForm.external_reply_url || null,
      mention_url: replyForm.mention_url || null,
    })
  }

  const selectedAccount = accounts.find(a => a.id === selected)

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Cuentas de Respuesta</h1>
          <p className="text-gray-500 text-sm mt-0.5">Cuentas del equipo que responden a posts monitoreados</p>
        </div>
        <button onClick={openCreate} className="btn-primary">
          <Plus className="w-4 h-4" /> Nueva cuenta
        </button>
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4">
        <div className="card text-center">
          <p className="text-2xl font-bold text-primary-700">{stats.active_accounts ?? '—'}</p>
          <p className="text-xs text-gray-500 mt-0.5">Cuentas activas</p>
        </div>
        <div className="card text-center">
          <p className="text-2xl font-bold text-gray-900">{stats.total_replies ?? '—'}</p>
          <p className="text-xs text-gray-500 mt-0.5">Respuestas registradas</p>
        </div>
        <div className="card text-center">
          <p className="text-2xl font-bold text-green-700">{stats.posts_covered ?? '—'}</p>
          <p className="text-xs text-gray-500 mt-0.5">Posts atendidos</p>
        </div>
        <div className="card text-center">
          <p className="text-2xl font-bold text-blue-700">{stats.auto_detected_total ?? '—'}</p>
          <p className="text-xs text-gray-500 mt-0.5">Detectadas auto</p>
        </div>
        <div className="card text-center">
          <p className="text-lg font-bold text-purple-700 truncate">
            {stats.top_account ? `@${stats.top_account.username}` : '—'}
          </p>
          <p className="text-xs text-gray-500 mt-0.5">
            {stats.top_account ? `${stats.top_account.total_replies} respuestas` : 'Cuenta más activa'}
          </p>
        </div>
      </div>

      {/* Tabla de cuentas */}
      <div className="card p-0 overflow-hidden">
        <div className="px-5 py-4 border-b border-gray-100">
          <h2 className="font-semibold text-gray-800">Cuentas registradas</h2>
        </div>
        {isLoading ? (
          <div className="text-center text-gray-400 py-12">Cargando cuentas...</div>
        ) : accounts.length === 0 ? (
          <div className="text-center py-16 text-gray-400">
            <MessageSquareReply className="w-10 h-10 mx-auto mb-3 opacity-30" />
            <p className="font-medium">No hay cuentas registradas</p>
            <p className="text-sm mt-1">Agrega la primera con el botón "Nueva cuenta"</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 border-b border-gray-100">
                <tr>
                  <th className="text-left px-5 py-3 font-medium text-gray-600">Cuenta</th>
                  <th className="hidden sm:table-cell text-left px-5 py-3 font-medium text-gray-600">Descripción</th>
                  <th className="text-right px-5 py-3 font-medium text-gray-600">Respuestas</th>
                  <th className="hidden md:table-cell text-right px-5 py-3 font-medium text-gray-600">Auto det.</th>
                  <th className="hidden md:table-cell text-right px-5 py-3 font-medium text-gray-600">Posts</th>
                  <th className="hidden lg:table-cell text-left px-5 py-3 font-medium text-gray-600">Última respuesta</th>
                  <th className="text-left px-5 py-3 font-medium text-gray-600">Estado</th>
                  <th className="px-5 py-3" />
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {accounts.map(account => (
                  <tr key={account.id}
                      className={`hover:bg-gray-50 cursor-pointer ${selected === account.id ? 'bg-primary-50' : ''}`}
                      onClick={() => setSelected(selected === account.id ? null : account.id)}>
                    <td className="px-5 py-3">
                      <div className="flex items-center gap-2">
                        <span className="text-lg">{PLATFORM_ICON[(account.platform?.name || '').toLowerCase()] ?? '🌐'}</span>
                        <div>
                          <p className="font-semibold text-gray-900">@{account.username}</p>
                          {account.display_name && (
                            <p className="text-xs text-gray-400">{account.display_name}</p>
                          )}
                        </div>
                      </div>
                    </td>
                    <td className="hidden sm:table-cell px-5 py-3 text-gray-500 max-w-[200px] truncate">
                      {account.description || '—'}
                    </td>
                    <td className="px-5 py-3 text-right font-semibold text-gray-900">
                      {account.total_replies}
                    </td>
                    <td className="hidden md:table-cell px-5 py-3 text-right text-blue-600 font-medium">
                      {account.auto_detected_count ?? 0}
                    </td>
                    <td className="hidden md:table-cell px-5 py-3 text-right text-gray-600">
                      {account.unique_posts_covered}
                    </td>
                    <td className="hidden lg:table-cell px-5 py-3 text-gray-400 text-xs">
                      {fmtDate(account.last_reply_at)}
                    </td>
                    <td className="px-5 py-3">
                      <span className={`badge ${account.active ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'}`}>
                        {account.active ? 'Activa' : 'Inactiva'}
                      </span>
                    </td>
                    <td className="px-5 py-3" onClick={e => e.stopPropagation()}>
                      <div className="flex items-center justify-end gap-1.5">
                        <button
                          onClick={() => openEdit(account)}
                          className="text-xs px-2.5 py-1 rounded-lg border border-gray-200 text-gray-600 hover:bg-gray-50">
                          <Pencil className="w-3.5 h-3.5 inline mr-1" />Editar
                        </button>
                        <button
                          onClick={() => toggleActive.mutate({ id: account.id, active: account.active })}
                          className={`text-xs px-2.5 py-1 rounded-lg border ${account.active
                            ? 'border-amber-200 text-amber-600 hover:bg-amber-50'
                            : 'border-green-200 text-green-600 hover:bg-green-50'}`}>
                          {account.active
                            ? <><UserX className="w-3.5 h-3.5 inline mr-1" />Desactivar</>
                            : <><UserCheck className="w-3.5 h-3.5 inline mr-1" />Activar</>}
                        </button>
                        <button
                          onClick={() => {
                            if (confirm(`¿Eliminar la cuenta @${account.username}? Se borrará también su historial de respuestas.`)) {
                              deleteAccount.mutate(account.id)
                            }
                          }}
                          className="text-xs px-2.5 py-1 rounded-lg border border-red-200 text-red-600 hover:bg-red-50">
                          <Trash2 className="w-3.5 h-3.5 inline mr-1" />Eliminar
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Panel de historial */}
      {selected && selectedAccount && (
        <div className="card">
          <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
            <div className="flex items-center gap-2">
              <span className="text-lg">{PLATFORM_ICON[(selectedAccount.platform?.name || '').toLowerCase()] ?? '🌐'}</span>
              <h2 className="font-semibold text-gray-800">@{selectedAccount.username} — Historial de Respuestas</h2>
            </div>
            <div className="flex gap-2">
              <button onClick={() => setShowReplyModal(true)} className="btn-primary text-sm py-1.5">
                <Plus className="w-4 h-4" /> Registrar respuesta
              </button>
              <button onClick={() => setSelected(null)} className="btn-secondary text-sm py-1.5">
                <X className="w-4 h-4" />
              </button>
            </div>
          </div>

          {loadingReplies ? (
            <div className="text-center text-gray-400 py-8">Cargando historial...</div>
          ) : replies.length === 0 ? (
            <div className="text-center py-12 text-gray-400">
              <MessageSquareReply className="w-8 h-8 mx-auto mb-2 opacity-30" />
              <p className="text-sm">Esta cuenta aún no tiene respuestas registradas</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-[600px] w-full text-sm">
                <thead>
                  <tr className="text-xs text-gray-500 border-b">
                    <th className="text-left pb-2 font-medium">Fecha respuesta</th>
                    <th className="text-left pb-2 font-medium">Origen</th>
                    <th className="text-left pb-2 font-medium">Post original</th>
                    <th className="text-left pb-2 font-medium">Contenido de la respuesta</th>
                    <th className="text-left pb-2 font-medium">Registrado por</th>
                    <th className="pb-2" />
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {replies.map(reply => (
                    <tr key={reply.id} className="hover:bg-gray-50">
                      <td className="py-3 text-gray-500 text-xs whitespace-nowrap pr-3">
                        {fmtDate(reply.replied_at)}
                        {reply.response_time_hours != null && (
                          <p className="text-gray-400 mt-0.5">+{reply.response_time_hours}h</p>
                        )}
                      </td>
                      <td className="py-3 pr-3 whitespace-nowrap">
                        {reply.auto_detected ? (
                          <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-blue-100 text-blue-700">Auto</span>
                        ) : (
                          <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-500">Manual</span>
                        )}
                      </td>
                      <td className="py-3 pr-4 max-w-[200px]">
                        {reply.mention ? (
                          <div>
                            <p className="text-xs text-gray-400 mb-0.5">
                              {reply.mention.platform} · @{reply.mention.author_username || '—'}
                            </p>
                            <p className="text-gray-700 text-xs line-clamp-2">{reply.mention.content_preview}</p>
                          </div>
                        ) : (
                          <span className="text-gray-400 text-xs italic">Sin post vinculado</span>
                        )}
                      </td>
                      <td className="py-3 pr-4 max-w-[250px]">
                        <p className="text-gray-800 text-xs line-clamp-3">{reply.content}</p>
                      </td>
                      <td className="py-3 text-xs text-gray-400 whitespace-nowrap">
                        {reply.logged_by_username ? `@${reply.logged_by_username}` : <span className="italic">sistema</span>}
                      </td>
                      <td className="py-3">
                        {reply.external_reply_url && (
                          <a href={reply.external_reply_url} target="_blank" rel="noreferrer"
                             className="text-primary-600 hover:text-primary-800">
                            <ExternalLink className="w-4 h-4" />
                          </a>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Modal: Nueva / Editar cuenta */}
      {showAccountModal && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-md p-6">
            <div className="flex items-center justify-between mb-5">
              <h2 className="font-semibold text-gray-900">
                {editingAccount ? 'Editar cuenta' : 'Nueva cuenta de respuesta'}
              </h2>
              <button onClick={() => setShowAccountModal(false)} className="text-gray-400 hover:text-gray-600">
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="space-y-4">
              {!editingAccount && (
                <div>
                  <label className="label">Plataforma *</label>
                  <select className="input"
                    value={accountForm.platform_id}
                    onChange={e => setAccountForm(f => ({ ...f, platform_id: e.target.value }))}>
                    <option value="">Seleccionar plataforma</option>
                    {platforms.map(p => (
                      <option key={p.id} value={p.id}>{p.name}</option>
                    ))}
                  </select>
                </div>
              )}
              <div>
                <label className="label">@Usuario *</label>
                <input className="input" placeholder="sonar_respuesta"
                  value={accountForm.username}
                  onChange={e => setAccountForm(f => ({ ...f, username: e.target.value }))} />
              </div>
              <div>
                <label className="label">Nombre visible</label>
                <input className="input" placeholder="Cuenta oficial SONAR"
                  value={accountForm.display_name}
                  onChange={e => setAccountForm(f => ({ ...f, display_name: e.target.value }))} />
              </div>
              <div>
                <label className="label">Descripción</label>
                <textarea className="input" rows={2} placeholder="Propósito de esta cuenta..."
                  value={accountForm.description}
                  onChange={e => setAccountForm(f => ({ ...f, description: e.target.value }))} />
              </div>
            </div>
            <div className="flex gap-2 mt-6">
              <button
                onClick={submitAccount}
                disabled={createAccount.isPending || updateAccount.isPending || !accountForm.username || (!editingAccount && !accountForm.platform_id)}
                className="btn-primary flex-1">
                {(createAccount.isPending || updateAccount.isPending) ? 'Guardando...' : 'Guardar'}
              </button>
              <button onClick={() => setShowAccountModal(false)} className="btn-secondary">Cancelar</button>
            </div>
          </div>
        </div>
      )}

      {/* Modal: Registrar respuesta */}
      {showReplyModal && selected && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-lg p-6">
            <div className="flex items-center justify-between mb-5">
              <div>
                <h2 className="font-semibold text-gray-900">Registrar respuesta</h2>
                <p className="text-xs text-gray-400 mt-0.5">Cuenta: @{selectedAccount?.username}</p>
              </div>
              <button onClick={() => setShowReplyModal(false)} className="text-gray-400 hover:text-gray-600">
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="space-y-4">
              <div>
                <label className="label">Fecha y hora de la respuesta *</label>
                <input className="input" type="datetime-local"
                  value={replyForm.replied_at}
                  onChange={e => setReplyForm(f => ({ ...f, replied_at: e.target.value }))} />
              </div>
              <div>
                <label className="label">Contenido de la respuesta *</label>
                <textarea className="input" rows={4}
                  placeholder="Texto que publicó la cuenta en la plataforma..."
                  value={replyForm.content}
                  onChange={e => setReplyForm(f => ({ ...f, content: e.target.value }))} />
              </div>
              <div>
                <label className="label">URL del post original</label>
                <input className="input" placeholder="https://twitter.com/... (opcional)"
                  value={replyForm.mention_url}
                  onChange={e => setReplyForm(f => ({ ...f, mention_url: e.target.value }))} />
                <p className="text-xs text-gray-400 mt-1">Si la URL coincide con una mención registrada, se vinculará automáticamente.</p>
              </div>
              <div>
                <label className="label">URL de la respuesta publicada</label>
                <input className="input" placeholder="https://twitter.com/sonar_respuesta/... (opcional)"
                  value={replyForm.external_reply_url}
                  onChange={e => setReplyForm(f => ({ ...f, external_reply_url: e.target.value }))} />
              </div>
            </div>
            <div className="flex gap-2 mt-6">
              <button
                onClick={submitReply}
                disabled={logReply.isPending || !replyForm.content || !replyForm.replied_at}
                className="btn-primary flex-1">
                {logReply.isPending ? 'Guardando...' : 'Registrar respuesta'}
              </button>
              <button onClick={() => setShowReplyModal(false)} className="btn-secondary">Cancelar</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
