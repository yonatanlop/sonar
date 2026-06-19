/**
 * Grupos administrar y cerrar — registro de grupos de Facebook a cerrar.
 * Guarda URL, razón, fecha de inicio del proceso y fecha fin.
 * El estado (En proceso / Cerrado) se deriva de la fecha fin.
 */
import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { UsersRound, Plus, Pencil, Trash2, X, ExternalLink, AlertCircle, CheckCircle, Clock } from 'lucide-react'
import toast from 'react-hot-toast'
import client from '../api/client'

const fetchGroups = () => client.get('/facebook-groups').then(r => r.data)

function fmtDate(dt) {
  if (!dt) return '—'
  return new Date(dt).toLocaleDateString('es', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' })
}

// ISO → valor para <input type="datetime-local"> (hora local)
function toLocalInput(dt) {
  if (!dt) return ''
  const d = new Date(dt)
  const off = d.getTimezoneOffset()
  return new Date(d.getTime() - off * 60000).toISOString().slice(0, 16)
}

const EMPTY = { group_url: '', reason: '', start_date: '', end_date: '' }

export default function FacebookGroups() {
  const qc = useQueryClient()
  const [showModal, setShowModal] = useState(false)
  const [editing, setEditing]     = useState(null)
  const [form, setForm]           = useState(EMPTY)

  const { data: groups = [], isLoading } = useQuery({
    queryKey: ['facebook-groups'],
    queryFn: fetchGroups,
  })

  const invalidate = () => qc.invalidateQueries({ queryKey: ['facebook-groups'] })

  const createMut = useMutation({
    mutationFn: (body) => client.post('/facebook-groups', body),
    onSuccess: () => { toast.success('Grupo registrado'); invalidate(); closeModal() },
    onError: (e) => toast.error(e.response?.data?.detail || 'Error al registrar'),
  })

  const updateMut = useMutation({
    mutationFn: ({ id, body }) => client.put(`/facebook-groups/${id}`, body),
    onSuccess: () => { toast.success('Grupo actualizado'); invalidate(); closeModal() },
    onError: (e) => toast.error(e.response?.data?.detail || 'Error al actualizar'),
  })

  const deleteMut = useMutation({
    mutationFn: (id) => client.delete(`/facebook-groups/${id}`),
    onSuccess: () => { toast.success('Grupo eliminado'); invalidate() },
    onError: (e) => toast.error(e.response?.data?.detail || 'Error al eliminar'),
  })

  function openCreate() { setEditing(null); setForm(EMPTY); setShowModal(true) }
  function openEdit(g) {
    setEditing(g)
    setForm({
      group_url: g.group_url,
      reason: g.reason || '',
      start_date: toLocalInput(g.start_date),
      end_date: toLocalInput(g.end_date),
    })
    setShowModal(true)
  }
  function closeModal() { setShowModal(false); setEditing(null); setForm(EMPTY) }

  function submit() {
    if (!form.group_url.trim()) { toast.error('La URL del grupo es obligatoria'); return }
    if (!form.start_date) { toast.error('La fecha de inicio es obligatoria'); return }
    const body = {
      group_url: form.group_url.trim(),
      reason: form.reason.trim() || null,
      start_date: new Date(form.start_date).toISOString(),
      end_date: form.end_date ? new Date(form.end_date).toISOString() : null,
    }
    if (editing) updateMut.mutate({ id: editing.id, body })
    else createMut.mutate(body)
  }

  const saving = createMut.isPending || updateMut.isPending
  const closedCount = groups.filter(g => g.status === 'cerrado').length

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-2">
          <UsersRound className="w-6 h-6 text-primary-600" />
          <div>
            <h1 className="text-xl font-bold text-gray-900">Grupos administrar y cerrar</h1>
            <p className="text-sm text-gray-500">
              Registro de grupos de Facebook a cerrar · {closedCount} de {groups.length} cerrados
            </p>
          </div>
        </div>
        <button onClick={openCreate} className="btn-primary flex items-center gap-1.5">
          <Plus className="w-4 h-4" /> Nuevo grupo
        </button>
      </div>

      {/* Tabla */}
      <div className="card p-0 overflow-hidden">
        {isLoading ? (
          <div className="text-center text-gray-400 py-12">Cargando grupos…</div>
        ) : groups.length === 0 ? (
          <div className="text-center py-16 text-gray-400">
            <AlertCircle className="w-10 h-10 mx-auto mb-3 opacity-30" />
            <p className="font-medium">No hay grupos registrados</p>
            <button onClick={openCreate} className="text-sm text-primary-600 hover:underline mt-2">+ Registrar el primero</button>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 border-b border-gray-100">
                <tr>
                  <th className="text-left px-5 py-3 font-medium text-gray-600">Grupo</th>
                  <th className="text-left px-5 py-3 font-medium text-gray-600">Razón</th>
                  <th className="text-left px-5 py-3 font-medium text-gray-600">Inicio</th>
                  <th className="text-left px-5 py-3 font-medium text-gray-600">Cierre</th>
                  <th className="text-left px-5 py-3 font-medium text-gray-600">Estado</th>
                  <th className="px-5 py-3" />
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {groups.map(g => (
                  <tr key={g.id} className="hover:bg-gray-50">
                    <td className="px-5 py-3 max-w-[240px]">
                      <a href={g.group_url} target="_blank" rel="noopener noreferrer"
                         className="text-primary-600 hover:underline flex items-center gap-1 truncate">
                        <span className="truncate">{g.group_url}</span>
                        <ExternalLink className="w-3 h-3 shrink-0" />
                      </a>
                    </td>
                    <td className="px-5 py-3 text-gray-600 max-w-[220px]">
                      <span className="line-clamp-2">{g.reason || '—'}</span>
                    </td>
                    <td className="px-5 py-3 text-gray-500 text-xs whitespace-nowrap">{fmtDate(g.start_date)}</td>
                    <td className="px-5 py-3 text-gray-500 text-xs whitespace-nowrap">{fmtDate(g.end_date)}</td>
                    <td className="px-5 py-3">
                      {g.status === 'cerrado' ? (
                        <span className="badge bg-green-100 text-green-700 flex items-center gap-1 w-fit">
                          <CheckCircle className="w-3 h-3" /> Cerrado
                        </span>
                      ) : (
                        <span className="badge bg-orange-100 text-orange-700 flex items-center gap-1 w-fit">
                          <Clock className="w-3 h-3" /> En proceso
                        </span>
                      )}
                    </td>
                    <td className="px-5 py-3">
                      <div className="flex items-center justify-end gap-1.5">
                        <button onClick={() => openEdit(g)}
                          className="text-xs px-2.5 py-1 rounded-lg border border-gray-200 text-gray-600 hover:bg-gray-50 flex items-center gap-1">
                          <Pencil className="w-3.5 h-3.5" /> Editar
                        </button>
                        <button
                          onClick={() => { if (confirm('¿Eliminar este registro de grupo?')) deleteMut.mutate(g.id) }}
                          className="text-xs px-2.5 py-1 rounded-lg border border-red-200 text-red-600 hover:bg-red-50 flex items-center gap-1">
                          <Trash2 className="w-3.5 h-3.5" /> Eliminar
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

      {/* Modal */}
      {showModal && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4" onClick={closeModal}>
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-md p-6" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-5">
              <h2 className="font-semibold text-gray-900">{editing ? 'Editar grupo' : 'Nuevo grupo a cerrar'}</h2>
              <button onClick={closeModal} className="text-gray-400 hover:text-gray-600"><X className="w-5 h-5" /></button>
            </div>
            <div className="space-y-4">
              <div>
                <label className="label">URL del grupo *</label>
                <input className="input w-full" placeholder="https://www.facebook.com/groups/..."
                  value={form.group_url}
                  onChange={e => setForm(f => ({ ...f, group_url: e.target.value }))} />
              </div>
              <div>
                <label className="label">Razón del cierre</label>
                <textarea className="input w-full resize-none" rows={2} placeholder="Por qué se cierra el grupo…"
                  value={form.reason}
                  onChange={e => setForm(f => ({ ...f, reason: e.target.value }))} />
              </div>
              <div>
                <label className="label">Fecha de inicio del cierre *</label>
                <input className="input w-full" type="datetime-local"
                  value={form.start_date}
                  onChange={e => setForm(f => ({ ...f, start_date: e.target.value }))} />
              </div>
              <div>
                <label className="label">Fecha fin (cuando se logró cerrar)</label>
                <input className="input w-full" type="datetime-local"
                  value={form.end_date}
                  onChange={e => setForm(f => ({ ...f, end_date: e.target.value }))} />
                <p className="text-xs text-gray-400 mt-1">Déjala vacía mientras el cierre esté en proceso.</p>
              </div>
            </div>
            <div className="flex gap-2 mt-6">
              <button onClick={submit} disabled={saving} className="btn-primary flex-1">
                {saving ? 'Guardando…' : 'Guardar'}
              </button>
              <button onClick={closeModal} className="btn-secondary">Cancelar</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
