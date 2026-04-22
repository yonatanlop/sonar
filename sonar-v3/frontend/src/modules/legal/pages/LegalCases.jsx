import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { Plus, Scale } from 'lucide-react'
import { format } from 'date-fns'
import { es } from 'date-fns/locale'
import toast from 'react-hot-toast'
import client from '../../../shared/api/client'
import { useAuthStore } from '../../../shared/store/authStore'

const fetchCases    = (p) => client.get('/legal/cases', { params: p }).then(r => r.data)
const fetchEntities = () => client.get('/entities').then(r => r.data)

const LEVEL_LABEL  = { platform: 'Plataforma', mira_legal: 'Jurídico MIRA', church_legal: 'Jurídico Iglesia' }
const LEVEL_COLOR  = { platform: 'badge-low', mira_legal: 'badge-medium', church_legal: 'badge-high' }
const STATUS_LABEL = { open: 'Abierto', in_review: 'En revisión', escalated: 'Escalado', resolved: 'Resuelto', closed: 'Cerrado' }

export default function LegalCases() {
  const qc        = useQueryClient()
  const isAnalyst = useAuthStore(s => s.isAnalyst())
  const [filters, setFilters] = useState({ level: '', status: '' })
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState({ title: '', description: '', level: 'platform', entity_id: '' })
  const set = (k, v) => setForm(f => ({ ...f, [k]: v }))

  const { data: cases    = [], isLoading } = useQuery({
    queryKey: ['legal-cases', filters],
    queryFn: () => fetchCases(Object.fromEntries(Object.entries(filters).filter(([,v]) => v !== ''))),
  })
  const { data: entities = [] } = useQuery({ queryKey: ['entities'], queryFn: fetchEntities })

  const create = useMutation({
    mutationFn: (body) => client.post('/legal/cases', body),
    onSuccess: () => {
      toast.success('Caso creado')
      qc.invalidateQueries({ queryKey: ['legal-cases'] })
      setShowForm(false)
      setForm({ title: '', description: '', level: 'platform', entity_id: '' })
    },
    onError: (e) => toast.error(e?.response?.data?.detail ?? 'Error'),
  })

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Casos Legales</h1>
          <p className="text-gray-500 text-sm mt-0.5">Gestión de escalación jurídica en 3 niveles</p>
        </div>
        {isAnalyst && !showForm && (
          <button className="btn-primary" onClick={() => setShowForm(true)}>
            <Plus className="w-4 h-4" /> Nuevo caso
          </button>
        )}
      </div>

      {showForm && (
        <form onSubmit={e => { e.preventDefault(); create.mutate(form) }} className="card space-y-4">
          <h2 className="font-semibold text-gray-800">Nuevo caso legal</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="sm:col-span-2">
              <label className="label">Título</label>
              <input className="input" value={form.title} onChange={e => set('title', e.target.value)} required />
            </div>
            <div>
              <label className="label">Nivel inicial</label>
              <select className="input" value={form.level} onChange={e => set('level', e.target.value)}>
                <option value="platform">Plataforma</option>
                <option value="mira_legal">Jurídico MIRA</option>
                <option value="church_legal">Jurídico Iglesia</option>
              </select>
            </div>
            <div>
              <label className="label">Entidad relacionada</label>
              <select className="input" value={form.entity_id} onChange={e => set('entity_id', e.target.value)}>
                <option value="">Sin entidad</option>
                {entities.map(e => <option key={e.id} value={e.id}>{e.name}</option>)}
              </select>
            </div>
            <div className="sm:col-span-2">
              <label className="label">Descripción</label>
              <textarea className="input" rows={3} value={form.description}
                onChange={e => set('description', e.target.value)} />
            </div>
          </div>
          <div className="flex gap-2">
            <button type="submit" className="btn-primary" disabled={create.isPending}>
              {create.isPending ? 'Guardando...' : 'Crear caso'}
            </button>
            <button type="button" className="btn-secondary" onClick={() => setShowForm(false)}>Cancelar</button>
          </div>
        </form>
      )}

      {/* Filtros */}
      <div className="card py-4">
        <div className="flex flex-wrap gap-3">
          <select className="input w-auto" value={filters.level} onChange={e => setFilters(f => ({ ...f, level: e.target.value }))}>
            <option value="">Todos los niveles</option>
            {Object.entries(LEVEL_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
          <select className="input w-auto" value={filters.status} onChange={e => setFilters(f => ({ ...f, status: e.target.value }))}>
            <option value="">Todos los estados</option>
            {Object.entries(STATUS_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
        </div>
      </div>

      {isLoading ? (
        <div className="text-center text-gray-400 py-12">Cargando...</div>
      ) : (
        <div className="space-y-3">
          {cases.map(c => (
            <div key={c.id} className="card p-4 hover:shadow-md transition-shadow">
              <div className="flex items-start gap-3">
                <Scale className="w-5 h-5 text-primary-400 shrink-0 mt-0.5" />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap mb-1">
                    <Link to={`/legal/${c.id}`}
                      className="font-semibold text-gray-900 hover:text-primary-600 truncate">
                      {c.title}
                    </Link>
                    <span className={`badge ${LEVEL_COLOR[c.level]} shrink-0`}>{LEVEL_LABEL[c.level]}</span>
                    <span className={`badge badge-${c.status} shrink-0`}>{STATUS_LABEL[c.status]}</span>
                  </div>
                  {c.description && (
                    <p className="text-sm text-gray-600 truncate">{c.description}</p>
                  )}
                  <p className="text-xs text-gray-400 mt-1">
                    Creado {format(new Date(c.created_at), "d MMM yyyy", { locale: es })}
                    {' · '}{c.events?.length ?? 0} eventos
                  </p>
                </div>
              </div>
            </div>
          ))}
          {cases.length === 0 && (
            <div className="text-center text-gray-400 py-12">No hay casos con los filtros seleccionados</div>
          )}
        </div>
      )}
    </div>
  )
}
