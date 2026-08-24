/**
 * Seguimiento a caso — un caso agrupa múltiples publicaciones denunciadas.
 *
 * Vista lista: casos (nombre + imagen) con su conteo de registros y resueltos.
 * Vista detalle: registros del caso (publicación, denuncia, resultado), con
 * alta/edición/borrado de cada registro. El caso solo guarda nombre + imagen.
 */
import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  FolderSearch, Plus, Pencil, Trash2, X, ExternalLink, AlertCircle,
  CheckCircle, Clock, Camera, Upload, ArrowLeft, ListChecks,
} from 'lucide-react'
import toast from 'react-hot-toast'
import client from '../api/client'

const PLATFORMS = ['X', 'Facebook', 'YouTube', 'TikTok', 'Instagram']
const MAX_IMAGE_MB = 5

const fetchCases = () => client.get('/cases').then(r => r.data)
const fetchCase  = (id) => client.get(`/cases/${id}`).then(r => r.data)

function fmtDate(dt) {
  if (!dt) return '—'
  return new Date(dt).toLocaleDateString('es', { day: '2-digit', month: 'short', year: 'numeric' })
}

// ISO → valor para <input type="datetime-local"> (hora local)
function toLocalInput(dt) {
  if (!dt) return ''
  const d = new Date(dt)
  const off = d.getTimezoneOffset()
  return new Date(d.getTime() - off * 60000).toISOString().slice(0, 16)
}

const EMPTY_CASE   = { name: '', image: '' }
const EMPTY_RECORD = {
  publication_date: '', publication_url: '', platform: '',
  action_description: '', result: '', result_date: '',
}

export default function Cases() {
  const qc = useQueryClient()
  const [selectedId, setSelectedId] = useState(null)   // caso abierto (vista detalle) o null (lista)

  return selectedId
    ? <CaseDetail caseId={selectedId} onBack={() => setSelectedId(null)} qc={qc} />
    : <CaseList onOpen={setSelectedId} qc={qc} />
}


// ══════════════════════════════════════════════════════════════
//  Vista LISTA de casos
// ══════════════════════════════════════════════════════════════

function CaseList({ onOpen, qc }) {
  const [showModal, setShowModal] = useState(false)
  const [editing, setEditing]     = useState(null)
  const [form, setForm]           = useState(EMPTY_CASE)
  const [imageTouched, setImageTouched] = useState(false)
  const [loadingImg, setLoadingImg]     = useState(false)

  const { data: cases = [], isLoading } = useQuery({ queryKey: ['cases'], queryFn: fetchCases })
  const invalidate = () => qc.invalidateQueries({ queryKey: ['cases'] })

  const createMut = useMutation({
    mutationFn: (body) => client.post('/cases', body),
    onSuccess: () => { toast.success('Caso creado'); invalidate(); closeModal() },
    onError: (e) => toast.error(e.response?.data?.detail || 'Error al crear'),
  })
  const updateMut = useMutation({
    mutationFn: ({ id, body }) => client.put(`/cases/${id}`, body),
    onSuccess: () => { toast.success('Caso actualizado'); invalidate(); closeModal() },
    onError: (e) => toast.error(e.response?.data?.detail || 'Error al actualizar'),
  })
  const deleteMut = useMutation({
    mutationFn: (id) => client.delete(`/cases/${id}`),
    onSuccess: () => { toast.success('Caso eliminado'); invalidate() },
    onError: (e) => toast.error(e.response?.data?.detail || 'Error al eliminar'),
  })

  function openCreate() {
    setEditing(null); setForm(EMPTY_CASE); setImageTouched(false); setShowModal(true)
  }
  async function openEdit(c) {
    setEditing(c); setForm({ name: c.name || '', image: '' }); setImageTouched(false); setShowModal(true)
    if (c.has_image) {
      setLoadingImg(true)
      try {
        const detail = await fetchCase(c.id)
        setForm(f => ({ ...f, image: detail.image || '' }))
      } catch { /* editable igual sin previsualizar */ } finally { setLoadingImg(false) }
    }
  }
  function closeModal() {
    setShowModal(false); setEditing(null); setForm(EMPTY_CASE); setImageTouched(false)
  }
  function onSelectImage(e) {
    const file = e.target.files?.[0]
    e.target.value = ''
    if (!file) return
    if (!file.type.startsWith('image/')) { toast.error('El archivo debe ser una imagen'); return }
    if (file.size > MAX_IMAGE_MB * 1024 * 1024) { toast.error(`La imagen supera ${MAX_IMAGE_MB} MB`); return }
    const reader = new FileReader()
    reader.onload = () => { setForm(f => ({ ...f, image: reader.result })); setImageTouched(true) }
    reader.onerror = () => toast.error('No se pudo leer la imagen')
    reader.readAsDataURL(file)
  }
  function removeImage() { setForm(f => ({ ...f, image: '' })); setImageTouched(true) }

  function submit() {
    if (!form.name.trim()) { toast.error('El nombre del caso es obligatorio'); return }
    if (editing) {
      const body = { name: form.name.trim() }
      if (imageTouched) body.image = form.image || ''
      updateMut.mutate({ id: editing.id, body })
    } else {
      createMut.mutate({ name: form.name.trim(), image: form.image || null })
    }
  }

  const saving = createMut.isPending || updateMut.isPending
  const totalRecords = cases.reduce((n, c) => n + (c.record_count || 0), 0)

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-2">
          <FolderSearch className="w-6 h-6 text-primary-600" />
          <div>
            <h1 className="text-xl font-bold text-gray-900">Seguimiento a caso</h1>
            <p className="text-sm text-gray-500">
              {cases.length} {cases.length === 1 ? 'caso' : 'casos'} · {totalRecords} publicaciones en seguimiento
            </p>
          </div>
        </div>
        <button onClick={openCreate} className="btn-primary flex items-center gap-1.5">
          <Plus className="w-4 h-4" /> Nuevo caso
        </button>
      </div>

      <div className="card p-0 overflow-hidden">
        {isLoading ? (
          <div className="text-center text-gray-400 py-12">Cargando casos…</div>
        ) : cases.length === 0 ? (
          <div className="text-center py-16 text-gray-400">
            <AlertCircle className="w-10 h-10 mx-auto mb-3 opacity-30" />
            <p className="font-medium">No hay casos registrados</p>
            <button onClick={openCreate} className="text-sm text-primary-600 hover:underline mt-2">+ Crear el primero</button>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 border-b border-gray-100">
                <tr>
                  <th className="text-left px-5 py-3 font-medium text-gray-600">Caso</th>
                  <th className="text-left px-5 py-3 font-medium text-gray-600">Registros</th>
                  <th className="text-left px-5 py-3 font-medium text-gray-600">Progreso</th>
                  <th className="text-left px-5 py-3 font-medium text-gray-600">Creado</th>
                  <th className="px-5 py-3" />
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {cases.map(c => {
                  const total = c.record_count || 0
                  const done  = c.resolved_count || 0
                  const allDone = total > 0 && done === total
                  return (
                    <tr key={c.id} className="hover:bg-gray-50">
                      <td className="px-5 py-3 max-w-[280px]">
                        <button onClick={() => onOpen(c.id)}
                          className="flex items-center gap-2 text-left group">
                          {c.has_image && <Camera className="w-4 h-4 text-gray-400 shrink-0" />}
                          <span className="font-medium text-primary-700 group-hover:underline truncate">{c.name}</span>
                        </button>
                      </td>
                      <td className="px-5 py-3 text-gray-600 whitespace-nowrap">
                        <span className="inline-flex items-center gap-1.5">
                          <ListChecks className="w-4 h-4 text-gray-400" />
                          {total} {total === 1 ? 'registro' : 'registros'}
                        </span>
                      </td>
                      <td className="px-5 py-3">
                        {total === 0 ? (
                          <span className="text-gray-300">—</span>
                        ) : allDone ? (
                          <span className="badge bg-green-100 text-green-700 flex items-center gap-1 w-fit">
                            <CheckCircle className="w-3 h-3" /> {done}/{total} resueltos
                          </span>
                        ) : (
                          <span className="badge bg-orange-100 text-orange-700 flex items-center gap-1 w-fit">
                            <Clock className="w-3 h-3" /> {done}/{total} resueltos
                          </span>
                        )}
                      </td>
                      <td className="px-5 py-3 text-gray-500 text-xs whitespace-nowrap">{fmtDate(c.created_at)}</td>
                      <td className="px-5 py-3">
                        <div className="flex items-center justify-end gap-1.5">
                          <button onClick={() => onOpen(c.id)}
                            className="text-xs px-2.5 py-1 rounded-lg border border-primary-200 text-primary-700 hover:bg-primary-50">
                            Abrir
                          </button>
                          <button onClick={() => openEdit(c)}
                            className="text-xs px-2.5 py-1 rounded-lg border border-gray-200 text-gray-600 hover:bg-gray-50 flex items-center gap-1">
                            <Pencil className="w-3.5 h-3.5" /> Editar
                          </button>
                          <button
                            onClick={() => { if (confirm(`¿Eliminar el caso "${c.name}" y todos sus registros?`)) deleteMut.mutate(c.id) }}
                            className="text-xs px-2.5 py-1 rounded-lg border border-red-200 text-red-600 hover:bg-red-50 flex items-center gap-1">
                            <Trash2 className="w-3.5 h-3.5" /> Eliminar
                          </button>
                        </div>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Modal crear/editar caso */}
      {showModal && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4" onClick={closeModal}>
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-md p-6 max-h-[90vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-5">
              <h2 className="font-semibold text-gray-900">{editing ? 'Editar caso' : 'Nuevo caso'}</h2>
              <button onClick={closeModal} className="text-gray-400 hover:text-gray-600"><X className="w-5 h-5" /></button>
            </div>
            <div className="space-y-4">
              <div>
                <label className="label">Nombre del caso *</label>
                <input className="input w-full" placeholder='Ej: "Caso Payita"'
                  value={form.name}
                  onChange={e => setForm(f => ({ ...f, name: e.target.value }))} />
              </div>
              <div>
                <label className="label">Imagen (opcional)</label>
                {loadingImg ? (
                  <p className="text-xs text-gray-400 py-3">Cargando imagen…</p>
                ) : form.image ? (
                  <div className="relative inline-block">
                    <img src={form.image} alt="Vista previa" className="max-h-40 rounded-lg border border-gray-200" />
                    <button type="button" onClick={removeImage}
                      className="absolute -top-2 -right-2 bg-red-500 text-white rounded-full p-1 shadow hover:bg-red-600">
                      <X className="w-3.5 h-3.5" />
                    </button>
                  </div>
                ) : (
                  <label className="flex items-center gap-2 px-3 py-2 border border-dashed border-gray-300 rounded-lg text-sm text-gray-500 cursor-pointer hover:bg-gray-50 w-fit">
                    <Upload className="w-4 h-4" /> Subir imagen
                    <input type="file" accept="image/*" className="hidden" onChange={onSelectImage} />
                  </label>
                )}
                <p className="text-xs text-gray-400 mt-1">Formato imagen, máx {MAX_IMAGE_MB} MB.</p>
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


// ══════════════════════════════════════════════════════════════
//  Vista DETALLE de un caso (sus registros)
// ══════════════════════════════════════════════════════════════

function CaseDetail({ caseId, onBack, qc }) {
  const [showModal, setShowModal] = useState(false)
  const [editing, setEditing]     = useState(null)
  const [form, setForm]           = useState(EMPTY_RECORD)

  const { data: caso, isLoading } = useQuery({
    queryKey: ['case', caseId],
    queryFn: () => fetchCase(caseId),
  })

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ['case', caseId] })
    qc.invalidateQueries({ queryKey: ['cases'] })   // los conteos de la lista cambian
  }

  const createMut = useMutation({
    mutationFn: (body) => client.post(`/cases/${caseId}/records`, body),
    onSuccess: () => { toast.success('Registro agregado'); invalidate(); closeModal() },
    onError: (e) => toast.error(e.response?.data?.detail || 'Error al agregar'),
  })
  const updateMut = useMutation({
    mutationFn: ({ id, body }) => client.put(`/cases/${caseId}/records/${id}`, body),
    onSuccess: () => { toast.success('Registro actualizado'); invalidate(); closeModal() },
    onError: (e) => toast.error(e.response?.data?.detail || 'Error al actualizar'),
  })
  const deleteMut = useMutation({
    mutationFn: (id) => client.delete(`/cases/${caseId}/records/${id}`),
    onSuccess: () => { toast.success('Registro eliminado'); invalidate() },
    onError: (e) => toast.error(e.response?.data?.detail || 'Error al eliminar'),
  })

  function openCreate() { setEditing(null); setForm(EMPTY_RECORD); setShowModal(true) }
  function openEdit(r) {
    setEditing(r)
    setForm({
      publication_date: toLocalInput(r.publication_date),
      publication_url: r.publication_url || '',
      platform: r.platform || '',
      action_description: r.action_description || '',
      result: r.result || '',
      result_date: toLocalInput(r.result_date),
    })
    setShowModal(true)
  }
  function closeModal() { setShowModal(false); setEditing(null); setForm(EMPTY_RECORD) }

  function submit() {
    const body = {
      publication_date: form.publication_date ? new Date(form.publication_date).toISOString() : null,
      publication_url: form.publication_url.trim() || null,
      platform: form.platform || null,
      action_description: form.action_description.trim() || null,
      result: form.result.trim() || null,
      result_date: form.result_date ? new Date(form.result_date).toISOString() : null,
    }
    if (editing) updateMut.mutate({ id: editing.id, body })
    else createMut.mutate(body)
  }

  const saving  = createMut.isPending || updateMut.isPending
  const records = caso?.records || []
  const resolved = records.filter(r => r.result_date).length

  return (
    <div className="space-y-6">
      {/* Header del caso */}
      <div className="flex items-start justify-between flex-wrap gap-3">
        <div className="flex items-start gap-3">
          <button onClick={onBack}
            className="mt-1 p-1.5 rounded-lg border border-gray-200 text-gray-500 hover:bg-gray-50" title="Volver">
            <ArrowLeft className="w-4 h-4" />
          </button>
          {caso?.image && (
            <img src={caso.image} alt={caso.name}
              className="w-14 h-14 rounded-lg object-cover border border-gray-200" />
          )}
          <div>
            <h1 className="text-xl font-bold text-gray-900">{caso?.name || 'Caso'}</h1>
            <p className="text-sm text-gray-500">
              {records.length} {records.length === 1 ? 'registro' : 'registros'} · {resolved} resueltos
            </p>
          </div>
        </div>
        <button onClick={openCreate} className="btn-primary flex items-center gap-1.5">
          <Plus className="w-4 h-4" /> Agregar registro
        </button>
      </div>

      {/* Tabla de registros */}
      <div className="card p-0 overflow-hidden">
        {isLoading ? (
          <div className="text-center text-gray-400 py-12">Cargando…</div>
        ) : records.length === 0 ? (
          <div className="text-center py-16 text-gray-400">
            <AlertCircle className="w-10 h-10 mx-auto mb-3 opacity-30" />
            <p className="font-medium">Este caso aún no tiene registros</p>
            <button onClick={openCreate} className="text-sm text-primary-600 hover:underline mt-2">+ Agregar el primero</button>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 border-b border-gray-100">
                <tr>
                  <th className="text-left px-5 py-3 font-medium text-gray-600">Plataforma</th>
                  <th className="text-left px-5 py-3 font-medium text-gray-600">Publicación</th>
                  <th className="text-left px-5 py-3 font-medium text-gray-600">Estado</th>
                  <th className="text-left px-5 py-3 font-medium text-gray-600">Resultado</th>
                  <th className="px-5 py-3" />
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {records.map(r => (
                  <tr key={r.id} className="hover:bg-gray-50 align-top">
                    <td className="px-5 py-3">
                      {r.platform
                        ? <span className="badge bg-primary-50 text-primary-700 w-fit">{r.platform}</span>
                        : <span className="text-gray-300">—</span>}
                    </td>
                    <td className="px-5 py-3 text-gray-500 text-xs whitespace-nowrap">
                      {r.publication_url ? (
                        <a href={r.publication_url} target="_blank" rel="noopener noreferrer"
                           className="text-primary-600 hover:underline inline-flex items-center gap-1">
                          {fmtDate(r.publication_date)} <ExternalLink className="w-3 h-3" />
                        </a>
                      ) : fmtDate(r.publication_date)}
                    </td>
                    <td className="px-5 py-3">
                      {r.result_date ? (
                        <span className="badge bg-green-100 text-green-700 flex items-center gap-1 w-fit">
                          <CheckCircle className="w-3 h-3" /> Resuelto
                        </span>
                      ) : (
                        <span className="badge bg-orange-100 text-orange-700 flex items-center gap-1 w-fit">
                          <Clock className="w-3 h-3" /> En trámite
                        </span>
                      )}
                    </td>
                    <td className="px-5 py-3 text-gray-600 max-w-[280px]">
                      <span className="line-clamp-2">{r.result || '—'}</span>
                    </td>
                    <td className="px-5 py-3">
                      <div className="flex items-center justify-end gap-1.5">
                        <button onClick={() => openEdit(r)}
                          className="text-xs px-2.5 py-1 rounded-lg border border-gray-200 text-gray-600 hover:bg-gray-50 flex items-center gap-1">
                          <Pencil className="w-3.5 h-3.5" /> Editar
                        </button>
                        <button
                          onClick={() => { if (confirm('¿Eliminar este registro?')) deleteMut.mutate(r.id) }}
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

      {/* Modal crear/editar registro */}
      {showModal && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4" onClick={closeModal}>
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-lg p-6 max-h-[90vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-5">
              <h2 className="font-semibold text-gray-900">{editing ? 'Editar registro' : 'Nuevo registro'}</h2>
              <button onClick={closeModal} className="text-gray-400 hover:text-gray-600"><X className="w-5 h-5" /></button>
            </div>
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="label">Plataforma</label>
                  <select className="input w-full" value={form.platform}
                    onChange={e => setForm(f => ({ ...f, platform: e.target.value }))}>
                    <option value="">— Seleccionar —</option>
                    {PLATFORMS.map(p => <option key={p} value={p}>{p}</option>)}
                  </select>
                </div>
                <div>
                  <label className="label">Fecha de la publicación</label>
                  <input className="input w-full" type="datetime-local"
                    value={form.publication_date}
                    onChange={e => setForm(f => ({ ...f, publication_date: e.target.value }))} />
                </div>
              </div>
              <div>
                <label className="label">URL de la publicación</label>
                <input className="input w-full" placeholder="https://…"
                  value={form.publication_url}
                  onChange={e => setForm(f => ({ ...f, publication_url: e.target.value }))} />
              </div>
              <div>
                <label className="label">¿Qué se realizó en la denuncia?</label>
                <textarea className="input w-full resize-none" rows={3}
                  placeholder="Describe las acciones realizadas para denunciar la publicación…"
                  value={form.action_description}
                  onChange={e => setForm(f => ({ ...f, action_description: e.target.value }))} />
              </div>
              <div>
                <label className="label">Resultado de la denuncia</label>
                <textarea className="input w-full resize-none" rows={3}
                  placeholder="Describe el resultado obtenido…"
                  value={form.result}
                  onChange={e => setForm(f => ({ ...f, result: e.target.value }))} />
              </div>
              <div>
                <label className="label">Fecha de ejecución del resultado</label>
                <input className="input w-full" type="datetime-local"
                  value={form.result_date}
                  onChange={e => setForm(f => ({ ...f, result_date: e.target.value }))} />
                <p className="text-xs text-gray-400 mt-1">Déjala vacía mientras el registro siga en trámite.</p>
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
