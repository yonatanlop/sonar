import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Plus, Search, Building2, ChevronRight, ToggleLeft, ToggleRight } from 'lucide-react'
import toast from 'react-hot-toast'
import client from '../api/client'
import { useAuthStore } from '../store/authStore'

const fetchEntities = (q) => client.get('/entities', { params: { q } }).then(r => r.data)
const fetchTypes    = ()  => client.get('/entities/types').then(r => r.data)

const RISK_COLOR = { alto: 'text-red-600', medio: 'text-yellow-600', bajo: 'text-green-600' }

export default function Entities() {
  const qc        = useQueryClient()
  const isAnalyst = useAuthStore(s => s.isAnalyst())
  const [search, setSearch]     = useState('')
  const [showForm, setShowForm] = useState(false)
  const [form, setForm]         = useState({ name: '', entity_type_id: '', country_code: '', description: '', photo_url: '' })

  const { data: entities = [], isLoading } = useQuery({
    queryKey: ['entities', search],
    queryFn: () => fetchEntities(search),
  })
  const { data: types = [] } = useQuery({ queryKey: ['entity-types'], queryFn: fetchTypes })

  const create = useMutation({
    mutationFn: (body) => client.post('/entities', body),
    onSuccess: () => {
      toast.success('Entidad creada')
      qc.invalidateQueries({ queryKey: ['entities'] })
      setShowForm(false)
      setForm({ name: '', entity_type_id: '', country_code: '', description: '', photo_url: '' })
    },
  })

  const toggle = useMutation({
    mutationFn: ({ id, active }) => client.patch(`/entities/${id}`, { active: !active }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['entities'] }),
  })

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Entidades</h1>
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

      {/* Búsqueda */}
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
        <input className="input pl-9" placeholder="Buscar entidad..."
          value={search} onChange={e => setSearch(e.target.value)} />
      </div>

      {/* Listado */}
      {isLoading ? (
        <div className="text-center text-gray-400 py-12">Cargando entidades...</div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {entities.map(entity => (
            <div key={entity.id} className={`card hover:shadow-md transition-shadow ${!entity.active ? 'opacity-60' : ''}`}>
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
                  <button onClick={() => toggle.mutate({ id: entity.id, active: entity.active })}
                    className="text-gray-400 hover:text-primary-600 shrink-0">
                    {entity.active
                      ? <ToggleRight className="w-5 h-5 text-green-500" />
                      : <ToggleLeft className="w-5 h-5" />}
                  </button>
                )}
              </div>

              <div className="mt-3 flex items-center justify-between text-xs text-gray-500">
                <span>{entity.mention_count ?? 0} menciones hoy</span>
                {entity.risk_level && (
                  <span className={`font-semibold ${RISK_COLOR[entity.risk_level]}`}>
                    ● {entity.risk_level.toUpperCase()}
                  </span>
                )}
              </div>

              <Link to={`/entities/${entity.id}`}
                className="mt-3 flex items-center gap-1 text-xs text-primary-600 hover:underline">
                Ver detalle <ChevronRight className="w-3.5 h-3.5" />
              </Link>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
