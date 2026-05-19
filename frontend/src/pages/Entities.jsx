import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Plus, Search, Building2, ChevronRight, ToggleLeft, ToggleRight, EyeOff, RefreshCw, Pencil, X } from 'lucide-react'
import toast from 'react-hot-toast'
import client from '../api/client'
import { useAuthStore } from '../store/authStore'

const fetchEntities = (q) =>
  client.get('/entities', { params: { q, active_only: false } }).then(r => r.data)
const fetchTypes = () => client.get('/entities/types').then(r => r.data)

const RISK_COLOR = { alto: 'text-red-600', medio: 'text-yellow-600', bajo: 'text-green-600' }

const MONITORING_TYPE_OPTIONS = [
  { value: '',            label: 'Sin clasificar' },
  { value: 'reputation',  label: '🛡️ Vigilancia reputacional' },
  { value: 'political',   label: '🏛️ Seguimiento político' },
  { value: 'opportunity', label: '💡 Oportunidad del partido' },
]

const MONITORING_BADGE = {
  reputation:  { text: '🛡️ Reputacional', cls: 'bg-orange-100 text-orange-700 border-orange-200' },
  political:   { text: '🏛️ Político',     cls: 'bg-blue-100 text-blue-700 border-blue-200' },
  opportunity: { text: '💡 Oportunidad',  cls: 'bg-green-100 text-green-700 border-green-200' },
}

const MONITORING_BORDER = {
  reputation:  'border-t-2 border-t-orange-300',
  political:   'border-t-2 border-t-blue-400',
  opportunity: 'border-t-2 border-t-green-400',
}

const EMPTY_FORM = { name: '', entity_type_id: '', country_code: '', description: '', photo_url: '', monitoring_type: '' }

export default function Entities() {
  const qc        = useQueryClient()
  const isAnalyst = useAuthStore(s => s.isAnalyst())
  const [search, setSearch]         = useState('')
  const [showInactive, setShowInactive] = useState(false)
  const [filterMonitoring, setFilterMonitoring] = useState('')
  const [showForm, setShowForm]     = useState(false)
  const [form, setForm]             = useState(EMPTY_FORM)
  const [editingEntity, setEditingEntity] = useState(null)
  const [editForm, setEditForm]           = useState(EMPTY_FORM)

  function openEdit(entity) {
    setEditingEntity(entity)
    setEditForm({
      name:            entity.name            ?? '',
      entity_type_id:  entity.entity_type_id  ?? '',
      country_code:    entity.country_code    ?? '',
      description:     entity.description     ?? '',
      photo_url:       entity.photo_url       ?? '',
      monitoring_type: entity.monitoring_type ?? '',
    })
    setShowForm(false)
  }

  const { data: allEntities = [], isLoading } = useQuery({
    queryKey: ['entities', search],
    queryFn: () => fetchEntities(search),
  })
  const { data: types = [] } = useQuery({ queryKey: ['entity-types'], queryFn: fetchTypes })

  const inactiveCount = allEntities.filter(e => !e.active).length

  // Filtro cliente: activas/inactivas + tipo de monitoreo
  const entities = allEntities
    .filter(e => showInactive ? true : e.active)
    .filter(e => filterMonitoring ? e.monitoring_type === filterMonitoring : true)

  const create = useMutation({
    mutationFn: (body) => client.post('/entities', body),
    onSuccess: () => {
      toast.success('Entidad creada')
      qc.invalidateQueries({ queryKey: ['entities'] })
      setShowForm(false)
      setForm(EMPTY_FORM)
    },
  })

  const toggle = useMutation({
    mutationFn: ({ id, active }) => client.patch(`/entities/${id}`, { active: !active }),
    onSuccess: (_, { active }) => {
      toast.success(active ? 'Entidad desactivada' : 'Entidad reactivada')
      qc.invalidateQueries({ queryKey: ['entities'] })
    },
  })

  const editEntity = useMutation({
    mutationFn: ({ id, body }) => client.patch(`/entities/${id}`, body),
    onSuccess: () => {
      toast.success('Entidad actualizada')
      qc.invalidateQueries({ queryKey: ['entities'] })
      setEditingEntity(null)
    },
    onError: (err) => {
      toast.error(err?.response?.data?.detail ?? 'Error al actualizar la entidad')
    },
  })

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Líderes/Instituciones/Keywords</h1>
          <p className="text-gray-500 text-sm mt-0.5">Gestión de entidades monitoreadas</p>
        </div>
        {isAnalyst && (
          <button onClick={() => setShowForm(!showForm)} className="btn-primary">
            <Plus className="w-4 h-4" /> Nueva entidad
          </button>
        )}
      </div>

      {/* Formulario nueva entidad */}
      {showForm && (
        <div className="card border-primary-200 border-2">
          <h2 className="font-semibold mb-4">Nueva entidad</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="label">Nombre *</label>
              <input className="input" placeholder="Nombre completo"
                value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} />
            </div>
            <div>
              <label className="label">Tipo *</label>
              <select className="input" value={form.entity_type_id}
                onChange={e => setForm(f => ({ ...f, entity_type_id: e.target.value }))}>
                <option value="">Seleccionar tipo</option>
                {types.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
              </select>
            </div>
            <div>
              <label className="label">Tipo de monitoreo</label>
              <select className="input" value={form.monitoring_type}
                onChange={e => setForm(f => ({ ...f, monitoring_type: e.target.value }))}>
                {MONITORING_TYPE_OPTIONS.map(o => (
                  <option key={o.value} value={o.value}>{o.label}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="label">País</label>
              <input className="input" placeholder="CO, MX, US..."
                value={form.country_code} onChange={e => setForm(f => ({ ...f, country_code: e.target.value }))} />
            </div>
            <div>
              <label className="label">Descripción</label>
              <input className="input" placeholder="Descripción breve"
                value={form.description} onChange={e => setForm(f => ({ ...f, description: e.target.value }))} />
            </div>
            <div className="sm:col-span-2">
              <label className="label">URL de foto <span className="text-gray-400 font-normal">(opcional)</span></label>
              <input className="input" placeholder="https://ejemplo.com/foto.jpg"
                value={form.photo_url} onChange={e => setForm(f => ({ ...f, photo_url: e.target.value }))} />
            </div>
          </div>
          <div className="flex gap-2 mt-4">
            <button onClick={() => create.mutate(form)} disabled={create.isPending || !form.name || !form.entity_type_id}
              className="btn-primary">
              {create.isPending ? 'Guardando...' : 'Guardar'}
            </button>
            <button onClick={() => setShowForm(false)} className="btn-secondary">Cancelar</button>
          </div>
        </div>
      )}

      {/* Modal de edición de entidad */}
      {editingEntity && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4"
             onClick={() => setEditingEntity(null)}>
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-lg p-6"
               onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-4">
              <h2 className="font-semibold text-gray-900">Editar entidad</h2>
              <button onClick={() => setEditingEntity(null)} className="text-gray-400 hover:text-gray-600">
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="label">Nombre *</label>
                <input className="input" placeholder="Nombre completo"
                  value={editForm.name}
                  onChange={e => setEditForm(f => ({ ...f, name: e.target.value }))} />
              </div>
              <div>
                <label className="label">Tipo *</label>
                <select className="input" value={editForm.entity_type_id}
                  onChange={e => setEditForm(f => ({ ...f, entity_type_id: e.target.value }))}>
                  <option value="">Seleccionar tipo</option>
                  {types.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
                </select>
              </div>
              <div>
                <label className="label">Tipo de monitoreo</label>
                <select className="input" value={editForm.monitoring_type}
                  onChange={e => setEditForm(f => ({ ...f, monitoring_type: e.target.value }))}>
                  {MONITORING_TYPE_OPTIONS.map(o => (
                    <option key={o.value} value={o.value}>{o.label}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="label">País</label>
                <input className="input" placeholder="CO, MX, US..."
                  value={editForm.country_code}
                  onChange={e => setEditForm(f => ({ ...f, country_code: e.target.value }))} />
              </div>
              <div>
                <label className="label">Descripción</label>
                <input className="input" placeholder="Descripción breve"
                  value={editForm.description}
                  onChange={e => setEditForm(f => ({ ...f, description: e.target.value }))} />
              </div>
              <div className="sm:col-span-2">
                <label className="label">URL de foto <span className="text-gray-400 font-normal">(opcional)</span></label>
                <input className="input" placeholder="https://ejemplo.com/foto.jpg"
                  value={editForm.photo_url}
                  onChange={e => setEditForm(f => ({ ...f, photo_url: e.target.value }))} />
              </div>
            </div>
            <div className="flex gap-2 mt-6">
              <button
                onClick={() => {
                  const body = { ...editForm }
                  if (!body.country_code)    body.country_code    = null
                  if (!body.description)     body.description     = null
                  if (!body.photo_url)       body.photo_url       = null
                  if (!body.monitoring_type) body.monitoring_type = null
                  editEntity.mutate({ id: editingEntity.id, body })
                }}
                disabled={editEntity.isPending || !editForm.name || !editForm.entity_type_id}
                className="btn-primary flex-1">
                {editEntity.isPending ? 'Guardando...' : 'Guardar cambios'}
              </button>
              <button onClick={() => setEditingEntity(null)} className="btn-secondary">Cancelar</button>
            </div>
          </div>
        </div>
      )}

      {/* Barra de búsqueda + filtros */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="relative flex-1 min-w-[200px]">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
          <input className="input pl-9" placeholder="Buscar entidad..."
            value={search} onChange={e => setSearch(e.target.value)} />
        </div>

        {/* Filtro por tipo de monitoreo */}
        <div className="flex gap-1 flex-wrap">
          {[{ value: '', label: 'Todos' }, ...MONITORING_TYPE_OPTIONS.slice(1)].map(o => (
            <button
              key={o.value}
              onClick={() => setFilterMonitoring(o.value)}
              className={`px-3 py-1.5 rounded-full text-xs font-medium border transition-colors ${
                filterMonitoring === o.value
                  ? 'bg-primary-600 text-white border-primary-600'
                  : 'bg-white text-gray-600 border-gray-300 hover:border-primary-400'
              }`}
            >
              {o.label}
            </button>
          ))}
        </div>

        {/* Toggle inactivas — visible a todos; siempre aparece si hay inactivas */}
        {(inactiveCount > 0 || showInactive) && (
          <button
            onClick={() => setShowInactive(v => !v)}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium border transition-colors ${
              showInactive
                ? 'bg-gray-700 text-white border-gray-700'
                : 'bg-amber-50 text-amber-700 border-amber-400 hover:bg-amber-100'
            }`}
          >
            <EyeOff className="w-3.5 h-3.5" />
            {showInactive ? 'Ocultar inactivas' : `Mostrar inactivas (${inactiveCount})`}
          </button>
        )}
      </div>

      {/* Listado */}
      {isLoading ? (
        <div className="text-center text-gray-400 py-12">Cargando entidades...</div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {entities.map(entity => {
            const monBadge  = MONITORING_BADGE[entity.monitoring_type]
            const monBorder = MONITORING_BORDER[entity.monitoring_type] ?? ''
            return (
              <div
                key={entity.id}
                className={`card hover:shadow-md transition-shadow ${monBorder} ${
                  !entity.active ? 'opacity-50 bg-gray-50' : ''
                }`}
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="flex items-center gap-3 min-w-0">
                    <div className="w-10 h-10 rounded-full bg-primary-100 flex items-center justify-center shrink-0 overflow-hidden">
                      {entity.photo_url
                        ? <img src={entity.photo_url} alt={entity.name} className="w-10 h-10 rounded-full object-cover" />
                        : <Building2 className="w-5 h-5 text-primary-600" />}
                    </div>
                    <div className="min-w-0">
                      <p className="font-semibold text-gray-900 truncate">{entity.name}</p>
                      <p className="text-xs text-gray-500">{entity.type_name} · {entity.country_code ?? '—'}</p>
                    </div>
                  </div>
                  {isAnalyst && (
                    entity.active ? (
                      <button
                        onClick={() => toggle.mutate({ id: entity.id, active: entity.active })}
                        title="Desactivar entidad"
                        className="text-gray-400 hover:text-red-500 shrink-0 transition-colors"
                      >
                        <ToggleRight className="w-5 h-5 text-green-500" />
                      </button>
                    ) : (
                      <button
                        onClick={() => toggle.mutate({ id: entity.id, active: entity.active })}
                        className="flex items-center gap-1 px-2 py-1 rounded-md bg-green-100 text-green-700 hover:bg-green-200 text-xs font-semibold shrink-0 transition-colors"
                        title="Reactivar entidad"
                      >
                        <RefreshCw className="w-3 h-3" />
                        Reactivar
                      </button>
                    )
                  )}
                </div>

                <div className="mt-2 flex items-center gap-2 flex-wrap">
                  {monBadge && (
                    <span className={`text-xs px-2 py-0.5 rounded-full border font-medium ${monBadge.cls}`}>
                      {monBadge.text}
                    </span>
                  )}
                  {!entity.active && (
                    <span className="text-xs px-2 py-0.5 rounded-full bg-gray-200 text-gray-500 font-medium">
                      Inactiva
                    </span>
                  )}
                </div>

                <div className="mt-2 flex items-center justify-between text-xs text-gray-500">
                  <span>{entity.mention_count ?? 0} menciones hoy</span>
                  {entity.risk_level && (
                    <span className={`font-semibold ${RISK_COLOR[entity.risk_level]}`}>
                      ● {entity.risk_level.toUpperCase()}
                    </span>
                  )}
                </div>

                <div className="mt-3 flex items-center justify-between">
                  <Link to={`/entities/${entity.id}`}
                    className="flex items-center gap-1 text-xs text-primary-600 hover:underline">
                    Ver detalle <ChevronRight className="w-3.5 h-3.5" />
                  </Link>
                  {isAnalyst && (
                    <button
                      onClick={() => openEdit(entity)}
                      className="flex items-center gap-1 text-xs text-gray-400 hover:text-primary-600 transition-colors"
                      title="Editar entidad">
                      <Pencil className="w-3.5 h-3.5" /> Editar
                    </button>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
