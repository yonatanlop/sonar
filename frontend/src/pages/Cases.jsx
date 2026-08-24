/**
 * Seguimiento a caso — un caso agrupa múltiples publicaciones monitoreadas.
 *
 * Vista lista: casos (nombre + imagen) con conteo de registros y de publicaciones
 * eliminadas. Vista detalle: registros del caso con el esquema completo de la
 * matriz SONAR (publicación, perfil autor, análisis y denuncia).
 */
import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  FolderSearch, Plus, Pencil, Trash2, X, ExternalLink, AlertCircle,
  CheckCircle, Clock, Camera, Upload, ArrowLeft, ListChecks,
} from 'lucide-react'
import toast from 'react-hot-toast'
import client from '../api/client'

const MAX_IMAGE_MB = 5
const MEDIUMS      = ['X', 'Facebook', 'Instagram', 'TikTok', 'YouTube', 'Threads', 'Sitio Web']
const SENTIMENTS   = ['Positivo', 'Negativo', 'Neutral']
const FLAGS        = ['Rojo', 'Amarillo', 'Verde']
const MEDIA_TYPES  = ['Video', 'Publicación', 'Columna', 'Otro']
const AFFECTS_SUGGESTIONS = [
  'IDMJI', 'MIRA', 'Hna. María Luisa Piraquive', 'Hno. Carlos Alberto Baena',
  'Congresistas Bancada MIRA', 'Pastor', 'FIMLM', 'Ministerio',
]

const fetchCases  = () => client.get('/cases').then(r => r.data)
const fetchCase   = (id) => client.get(`/cases/${id}`).then(r => r.data)
const fetchRecord = (cid, rid) => client.get(`/cases/${cid}/records/${rid}`).then(r => r.data)

function fmtDate(dt) {
  if (!dt) return '—'
  return new Date(dt).toLocaleDateString('es', { day: '2-digit', month: 'short', year: 'numeric' })
}
function toLocalInput(dt) {
  if (!dt) return ''
  const d = new Date(dt)
  const off = d.getTimezoneOffset()
  return new Date(d.getTime() - off * 60000).toISOString().slice(0, 16)
}
// Booleanos tri-estado ⇄ select ('', 'si', 'no')
const boolToSel = (v) => (v === true ? 'si' : v === false ? 'no' : '')
const selToBool = (s) => (s === 'si' ? true : s === 'no' ? false : null)
// Números ⇄ texto de input
const numToStr = (n) => (n === null || n === undefined ? '' : String(n))
const strToNum = (s) => {
  const t = String(s ?? '').trim()
  if (t === '') return null
  const n = parseInt(t, 10)
  return Number.isFinite(n) ? n : null
}
const padId = (n) => (n == null ? '—' : String(n).padStart(4, '0'))

const EMPTY_CASE = { name: '', image: '' }
const EMPTY_RECORD = {
  affects: '', sentiment: '',
  publication_url: '', content_text: '', image: '', publication_date: '', medium: '', media_type: '',
  likes: '', shares: '', comments_count: '',
  author: '', user_id: '', account_age_months: '', followers: '', following: '', verified: '', bio: '', city: '',
  inauthenticity_flag: '', organic_criticism: '', opposition_criticism: '', coordinated_attack: '',
  reporter_name: '', reported: '', report_detail: '', post_removed: '',
}

export default function Cases() {
  const qc = useQueryClient()
  const [selectedId, setSelectedId] = useState(null)
  return selectedId
    ? <CaseDetail caseId={selectedId} onBack={() => setSelectedId(null)} qc={qc} />
    : <CaseList onOpen={setSelectedId} qc={qc} />
}


// ── Componentes de formulario reutilizables ───────────────────

function Field({ label, children, className = '' }) {
  return (
    <div className={className}>
      <label className="label">{label}</label>
      {children}
    </div>
  )
}
function YesNo({ value, onChange }) {
  return (
    <select className="input w-full" value={value} onChange={e => onChange(e.target.value)}>
      <option value="">—</option>
      <option value="si">Sí</option>
      <option value="no">No</option>
    </select>
  )
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

  function openCreate() { setEditing(null); setForm(EMPTY_CASE); setImageTouched(false); setShowModal(true) }
  async function openEdit(c) {
    setEditing(c); setForm({ name: c.name || '', image: '' }); setImageTouched(false); setShowModal(true)
    if (c.has_image) {
      setLoadingImg(true)
      try { const d = await fetchCase(c.id); setForm(f => ({ ...f, image: d.image || '' })) }
      catch { /* editable igual */ } finally { setLoadingImg(false) }
    }
  }
  function closeModal() { setShowModal(false); setEditing(null); setForm(EMPTY_CASE); setImageTouched(false) }
  function onSelectImage(e) {
    const file = e.target.files?.[0]; e.target.value = ''
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
                  <th className="text-left px-5 py-3 font-medium text-gray-600">Eliminadas</th>
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
                        <button onClick={() => onOpen(c.id)} className="flex items-center gap-2 text-left group">
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
                        ) : (
                          <span className={`badge flex items-center gap-1 w-fit ${allDone ? 'bg-green-100 text-green-700' : 'bg-orange-100 text-orange-700'}`}>
                            {allDone ? <CheckCircle className="w-3 h-3" /> : <Clock className="w-3 h-3" />}
                            {done}/{total} eliminadas
                          </span>
                        )}
                      </td>
                      <td className="px-5 py-3 text-gray-500 text-xs whitespace-nowrap">{fmtDate(c.created_at)}</td>
                      <td className="px-5 py-3">
                        <div className="flex items-center justify-end gap-1.5">
                          <button onClick={() => onOpen(c.id)}
                            className="text-xs px-2.5 py-1 rounded-lg border border-primary-200 text-primary-700 hover:bg-primary-50">Abrir</button>
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

      {showModal && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4" onClick={closeModal}>
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-md p-6 max-h-[90vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-5">
              <h2 className="font-semibold text-gray-900">{editing ? 'Editar caso' : 'Nuevo caso'}</h2>
              <button onClick={closeModal} className="text-gray-400 hover:text-gray-600"><X className="w-5 h-5" /></button>
            </div>
            <div className="space-y-4">
              <Field label="Nombre del caso *">
                <input className="input w-full" placeholder='Ej: "Caso Payita"'
                  value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} />
              </Field>
              <Field label="Imagen (opcional)">
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
              </Field>
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

function sentimentBadge(s) {
  const map = { Negativo: 'bg-red-100 text-red-700', Positivo: 'bg-green-100 text-green-700', Neutral: 'bg-gray-100 text-gray-600' }
  return map[s] || 'bg-gray-100 text-gray-600'
}
function flagBadge(f) {
  const map = { Rojo: 'bg-red-100 text-red-700', Amarillo: 'bg-yellow-100 text-yellow-700', Verde: 'bg-green-100 text-green-700' }
  return map[f] || 'bg-gray-100 text-gray-500'
}

function CaseDetail({ caseId, onBack, qc }) {
  const [showModal, setShowModal] = useState(false)
  const [editing, setEditing]     = useState(null)
  const [form, setForm]           = useState(EMPTY_RECORD)
  const [imageTouched, setImageTouched] = useState(false)
  const [loadingImg, setLoadingImg]     = useState(false)

  const { data: caso, isLoading } = useQuery({
    queryKey: ['case', caseId],
    queryFn: () => fetchCase(caseId),
  })

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ['case', caseId] })
    qc.invalidateQueries({ queryKey: ['cases'] })
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

  function openCreate() { setEditing(null); setForm(EMPTY_RECORD); setImageTouched(false); setShowModal(true) }
  async function openEdit(r) {
    setEditing(r)
    setForm({
      affects: r.affects || '', sentiment: r.sentiment || '',
      publication_url: r.publication_url || '', content_text: r.content_text || '', image: '',
      publication_date: toLocalInput(r.publication_date), medium: r.medium || '', media_type: r.media_type || '',
      likes: numToStr(r.likes), shares: numToStr(r.shares), comments_count: numToStr(r.comments_count),
      author: r.author || '', user_id: r.user_id || '', account_age_months: r.account_age_months || '',
      followers: numToStr(r.followers), following: numToStr(r.following), verified: boolToSel(r.verified),
      bio: r.bio || '', city: r.city || '',
      inauthenticity_flag: r.inauthenticity_flag || '',
      organic_criticism: boolToSel(r.organic_criticism), opposition_criticism: boolToSel(r.opposition_criticism),
      coordinated_attack: boolToSel(r.coordinated_attack),
      reporter_name: r.reporter_name || '', reported: boolToSel(r.reported),
      report_detail: r.report_detail || '', post_removed: boolToSel(r.post_removed),
    })
    setImageTouched(false); setShowModal(true)
    if (r.has_image) {
      setLoadingImg(true)
      try { const d = await fetchRecord(caseId, r.id); setForm(f => ({ ...f, image: d.image || '' })) }
      catch { /* editable igual */ } finally { setLoadingImg(false) }
    }
  }
  function closeModal() { setShowModal(false); setEditing(null); setForm(EMPTY_RECORD); setImageTouched(false) }
  function set(k, v) { setForm(f => ({ ...f, [k]: v })) }

  function onSelectImage(e) {
    const file = e.target.files?.[0]; e.target.value = ''
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
    const body = {
      affects: form.affects.trim() || null,
      sentiment: form.sentiment || null,
      publication_url: form.publication_url.trim() || null,
      content_text: form.content_text.trim() || null,
      publication_date: form.publication_date ? new Date(form.publication_date).toISOString() : null,
      medium: form.medium || null,
      media_type: form.media_type.trim() || null,
      likes: strToNum(form.likes), shares: strToNum(form.shares), comments_count: strToNum(form.comments_count),
      author: form.author.trim() || null,
      user_id: form.user_id.trim() || null,
      account_age_months: form.account_age_months.trim() || null,
      followers: strToNum(form.followers), following: strToNum(form.following),
      verified: selToBool(form.verified),
      bio: form.bio.trim() || null,
      city: form.city.trim() || null,
      inauthenticity_flag: form.inauthenticity_flag || null,
      organic_criticism: selToBool(form.organic_criticism),
      opposition_criticism: selToBool(form.opposition_criticism),
      coordinated_attack: selToBool(form.coordinated_attack),
      reporter_name: form.reporter_name.trim() || null,
      reported: selToBool(form.reported),
      report_detail: form.report_detail.trim() || null,
      post_removed: selToBool(form.post_removed),
    }
    // La imagen solo se envía si cambió (evita reenviar bytes)
    if (!editing) body.image = form.image || null
    else if (imageTouched) body.image = form.image || ''

    if (editing) updateMut.mutate({ id: editing.id, body })
    else createMut.mutate(body)
  }

  const saving  = createMut.isPending || updateMut.isPending
  const records = caso?.records || []
  const removed = records.filter(r => r.post_removed === true).length

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between flex-wrap gap-3">
        <div className="flex items-start gap-3">
          <button onClick={onBack}
            className="mt-1 p-1.5 rounded-lg border border-gray-200 text-gray-500 hover:bg-gray-50" title="Volver">
            <ArrowLeft className="w-4 h-4" />
          </button>
          {caso?.image && (
            <img src={caso.image} alt={caso.name} className="w-14 h-14 rounded-lg object-cover border border-gray-200" />
          )}
          <div>
            <h1 className="text-xl font-bold text-gray-900">{caso?.name || 'Caso'}</h1>
            <p className="text-sm text-gray-500">
              {records.length} {records.length === 1 ? 'registro' : 'registros'} · {removed} publicaciones eliminadas
            </p>
          </div>
        </div>
        <button onClick={openCreate} className="btn-primary flex items-center gap-1.5">
          <Plus className="w-4 h-4" /> Agregar registro
        </button>
      </div>

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
            <table className="w-full text-sm whitespace-nowrap">
              <thead className="bg-gray-50 border-b border-gray-100">
                <tr>
                  <th className="text-left px-4 py-3 font-medium text-gray-600">#</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-600">Afecta a</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-600">Medio</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-600">Publicación</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-600">Sentimiento</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-600">Inautenticidad</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-600">Denuncia</th>
                  <th className="px-4 py-3" />
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {records.map(r => (
                  <tr key={r.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3 text-gray-400 font-mono text-xs">{padId(r.post_id)}</td>
                    <td className="px-4 py-3 max-w-[180px]">
                      <div className="flex items-center gap-1.5">
                        {r.has_image && <Camera className="w-3.5 h-3.5 text-gray-400 shrink-0" />}
                        <span className="truncate text-gray-700">{r.affects || '—'}</span>
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      {r.medium ? <span className="badge bg-primary-50 text-primary-700 w-fit">{r.medium}</span> : <span className="text-gray-300">—</span>}
                    </td>
                    <td className="px-4 py-3 text-gray-500 text-xs">
                      {r.publication_url ? (
                        <a href={r.publication_url} target="_blank" rel="noopener noreferrer"
                           className="text-primary-600 hover:underline inline-flex items-center gap-1">
                          {fmtDate(r.publication_date)} <ExternalLink className="w-3 h-3" />
                        </a>
                      ) : fmtDate(r.publication_date)}
                    </td>
                    <td className="px-4 py-3">
                      {r.sentiment ? <span className={`badge w-fit ${sentimentBadge(r.sentiment)}`}>{r.sentiment}</span> : <span className="text-gray-300">—</span>}
                    </td>
                    <td className="px-4 py-3">
                      {r.inauthenticity_flag ? <span className={`badge w-fit ${flagBadge(r.inauthenticity_flag)}`}>{r.inauthenticity_flag}</span> : <span className="text-gray-300">—</span>}
                    </td>
                    <td className="px-4 py-3">
                      {r.post_removed === true ? (
                        <span className="badge bg-green-100 text-green-700 flex items-center gap-1 w-fit"><CheckCircle className="w-3 h-3" /> Eliminada</span>
                      ) : r.reported === true ? (
                        <span className="badge bg-orange-100 text-orange-700 flex items-center gap-1 w-fit"><Clock className="w-3 h-3" /> Denunciada</span>
                      ) : (
                        <span className="badge bg-gray-100 text-gray-500 w-fit">Sin denunciar</span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center justify-end gap-1.5">
                        <button onClick={() => openEdit(r)}
                          className="text-xs px-2.5 py-1 rounded-lg border border-gray-200 text-gray-600 hover:bg-gray-50 flex items-center gap-1">
                          <Pencil className="w-3.5 h-3.5" /> Editar
                        </button>
                        <button onClick={() => { if (confirm('¿Eliminar este registro?')) deleteMut.mutate(r.id) }}
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
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-2xl p-6 max-h-[92vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-5">
              <h2 className="font-semibold text-gray-900">
                {editing ? `Editar registro ${padId(editing.post_id)}` : 'Nuevo registro'}
              </h2>
              <button onClick={closeModal} className="text-gray-400 hover:text-gray-600"><X className="w-5 h-5" /></button>
            </div>

            <div className="space-y-6">
              {/* Publicación */}
              <section>
                <h3 className="text-xs font-semibold tracking-wider text-primary-600 uppercase mb-3">Publicación</h3>
                <div className="grid grid-cols-2 gap-3">
                  <Field label="A quién afecta este contenido">
                    <input className="input w-full" list="affects-list" placeholder="Ej: IDMJI, un líder…"
                      value={form.affects} onChange={e => set('affects', e.target.value)} />
                    <datalist id="affects-list">{AFFECTS_SUGGESTIONS.map(a => <option key={a} value={a} />)}</datalist>
                  </Field>
                  <Field label="Sentimiento">
                    <select className="input w-full" value={form.sentiment} onChange={e => set('sentiment', e.target.value)}>
                      <option value="">—</option>
                      {SENTIMENTS.map(s => <option key={s} value={s}>{s}</option>)}
                    </select>
                  </Field>
                  <Field label="Medio">
                    <select className="input w-full" value={form.medium} onChange={e => set('medium', e.target.value)}>
                      <option value="">—</option>
                      {MEDIUMS.map(m => <option key={m} value={m}>{m}</option>)}
                    </select>
                  </Field>
                  <Field label="Tipo de medio">
                    <input className="input w-full" list="mediatype-list" placeholder="Video, Publicación…"
                      value={form.media_type} onChange={e => set('media_type', e.target.value)} />
                    <datalist id="mediatype-list">{MEDIA_TYPES.map(t => <option key={t} value={t} />)}</datalist>
                  </Field>
                  <Field label="Fecha y hora de la publicación" className="col-span-2">
                    <input className="input w-full" type="datetime-local"
                      value={form.publication_date} onChange={e => set('publication_date', e.target.value)} />
                  </Field>
                  <Field label="Link de la publicación / comentario" className="col-span-2">
                    <input className="input w-full" placeholder="https://…"
                      value={form.publication_url} onChange={e => set('publication_url', e.target.value)} />
                  </Field>
                  <Field label="Texto del contenido" className="col-span-2">
                    <textarea className="input w-full resize-none" rows={2}
                      value={form.content_text} onChange={e => set('content_text', e.target.value)} />
                  </Field>
                  <div className="grid grid-cols-3 gap-3 col-span-2">
                    <Field label="N° Me gusta">
                      <input className="input w-full" type="number" min="0" value={form.likes} onChange={e => set('likes', e.target.value)} />
                    </Field>
                    <Field label="Compartidos / RT">
                      <input className="input w-full" type="number" min="0" value={form.shares} onChange={e => set('shares', e.target.value)} />
                    </Field>
                    <Field label="N° Comentarios">
                      <input className="input w-full" type="number" min="0" value={form.comments_count} onChange={e => set('comments_count', e.target.value)} />
                    </Field>
                  </div>
                  <Field label="Captura de imagen (opcional)" className="col-span-2">
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
                  </Field>
                </div>
              </section>

              {/* Perfil del autor */}
              <section>
                <h3 className="text-xs font-semibold tracking-wider text-primary-600 uppercase mb-3">Perfil del autor</h3>
                <div className="grid grid-cols-2 gap-3">
                  <Field label="Quién hace la publicación">
                    <input className="input w-full" value={form.author} onChange={e => set('author', e.target.value)} />
                  </Field>
                  <Field label="User ID">
                    <input className="input w-full" value={form.user_id} onChange={e => set('user_id', e.target.value)} />
                  </Field>
                  <Field label="Antigüedad de la cuenta (meses)">
                    <input className="input w-full" value={form.account_age_months} onChange={e => set('account_age_months', e.target.value)} />
                  </Field>
                  <Field label="Ciudad de origen">
                    <input className="input w-full" value={form.city} onChange={e => set('city', e.target.value)} />
                  </Field>
                  <Field label="N° Seguidores">
                    <input className="input w-full" type="number" min="0" value={form.followers} onChange={e => set('followers', e.target.value)} />
                  </Field>
                  <Field label="N° Seguidos">
                    <input className="input w-full" type="number" min="0" value={form.following} onChange={e => set('following', e.target.value)} />
                  </Field>
                  <Field label="¿Cuenta verificada?">
                    <YesNo value={form.verified} onChange={v => set('verified', v)} />
                  </Field>
                  <Field label="Biografía / descripción del perfil" className="col-span-2">
                    <textarea className="input w-full resize-none" rows={2}
                      value={form.bio} onChange={e => set('bio', e.target.value)} />
                  </Field>
                </div>
              </section>

              {/* Análisis */}
              <section>
                <h3 className="text-xs font-semibold tracking-wider text-primary-600 uppercase mb-3">Análisis</h3>
                <div className="grid grid-cols-2 gap-3">
                  <Field label="Semáforo de inautenticidad">
                    <select className="input w-full" value={form.inauthenticity_flag} onChange={e => set('inauthenticity_flag', e.target.value)}>
                      <option value="">—</option>
                      {FLAGS.map(f => <option key={f} value={f}>{f}</option>)}
                    </select>
                  </Field>
                  <Field label="¿Crítica orgánica de ciudadanos reales?">
                    <YesNo value={form.organic_criticism} onChange={v => set('organic_criticism', v)} />
                  </Field>
                  <Field label="¿Crítica impulsada por opositores?">
                    <YesNo value={form.opposition_criticism} onChange={v => set('opposition_criticism', v)} />
                  </Field>
                  <Field label="¿Ataque coordinado (CIB)?">
                    <YesNo value={form.coordinated_attack} onChange={v => set('coordinated_attack', v)} />
                  </Field>
                </div>
              </section>

              {/* Denuncia */}
              <section>
                <h3 className="text-xs font-semibold tracking-wider text-primary-600 uppercase mb-3">Denuncia</h3>
                <div className="grid grid-cols-2 gap-3">
                  <Field label="Nombre de quien reporta">
                    <input className="input w-full" value={form.reporter_name} onChange={e => set('reporter_name', e.target.value)} />
                  </Field>
                  <Field label="¿Se denunció?">
                    <YesNo value={form.reported} onChange={v => set('reported', v)} />
                  </Field>
                  <Field label="Detalle de la denuncia" className="col-span-2">
                    <textarea className="input w-full resize-none" rows={2}
                      placeholder="Qué se realizó en la denuncia…"
                      value={form.report_detail} onChange={e => set('report_detail', e.target.value)} />
                  </Field>
                  <Field label="¿La publicación fue eliminada?">
                    <YesNo value={form.post_removed} onChange={v => set('post_removed', v)} />
                  </Field>
                </div>
              </section>
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
