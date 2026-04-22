import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { Plus, Pencil, Eye } from 'lucide-react'
import toast from 'react-hot-toast'
import client from '../../../shared/api/client'
import { useAuthStore } from '../../../shared/store/authStore'

const fetchEntities = () => client.get('/entities').then(r => r.data)
const fetchTypes    = () => client.get('/entity-types').then(r => r.data)

function EntityForm({ initial, entityTypes, onSave, onCancel, isPending }) {
  const [form, setForm] = useState(initial ?? {
    name: '', entity_type_id: entityTypes?.[0]?.id ?? '', description: '', country_code: '', active: true,
  })
  const set = (k, v) => setForm(f => ({ ...f, [k]: v }))

  return (
    <form onSubmit={e => { e.preventDefault(); onSave(form) }}
      className="space-y-3 p-4 border border-gray-200 rounded-xl bg-gray-50">
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <div className="sm:col-span-2">
          <label className="label">Nombre</label>
          <input className="input" value={form.name} onChange={e => set('name', e.target.value)} required />
        </div>
        <div>
          <label className="label">Tipo</label>
          <select className="input" value={form.entity_type_id} onChange={e => set('entity_type_id', Number(e.target.value))}>
            {entityTypes?.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
          </select>
        </div>
        <div>
          <label className="label">País (código ISO 2)</label>
          <input className="input" maxLength={2} value={form.country_code} onChange={e => set('country_code', e.target.value.toUpperCase())} />
        </div>
        <div className="sm:col-span-2">
          <label className="label">Descripción</label>
          <textarea className="input" rows={2} value={form.description} onChange={e => set('description', e.target.value)} />
        </div>
      </div>
      <div className="flex gap-2">
        <button type="submit" className="btn-primary" disabled={isPending}>
          {isPending ? 'Guardando...' : initial ? 'Actualizar' : 'Crear entidad'}
        </button>
        <button type="button" className="btn-secondary" onClick={onCancel}>Cancelar</button>
      </div>
    </form>
  )
}

export default function Entities() {
  const qc = useQueryClient()
  const isAnalyst = useAuthStore(s => s.isAnalyst())
  const [showForm, setShowForm] = useState(false)
  const [editing, setEditing]   = useState(null)

  const { data: entities = [], isLoading } = useQuery({ queryKey: ['entities'], queryFn: fetchEntities })
  const { data: entityTypes = [] }         = useQuery({ queryKey: ['entity-types'], queryFn: fetchTypes })

  const create = useMutation({
    mutationFn: (body) => client.post('/entities', body),
    onSuccess: () => { toast.success('Entidad creada'); qc.invalidateQueries({ queryKey: ['entities'] }); setShowForm(false) },
    onError:   (e) => toast.error(e?.response?.data?.detail ?? 'Error'),
  })

  const update = useMutation({
    mutationFn: ({ id, ...body }) => client.patch(`/entities/${id}`, body),
    onSuccess: () => { toast.success('Entidad actualizada'); qc.invalidateQueries({ queryKey: ['entities'] }); setEditing(null) },
    onError:   (e) => toast.error(e?.response?.data?.detail ?? 'Error'),
  })

  if (isLoading) return <div className="text-center text-gray-400 py-12">Cargando...</div>

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Entidades</h1>
        {isAnalyst && !showForm && (
          <button className="btn-primary" onClick={() => setShowForm(true)}>
            <Plus className="w-4 h-4" /> Nueva entidad
          </button>
        )}
      </div>

      {showForm && (
        <EntityForm
          entityTypes={entityTypes}
          onSave={(form) => create.mutate(form)}
          onCancel={() => setShowForm(false)}
          isPending={create.isPending}
        />
      )}

      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
        {entities.map(entity => (
          <div key={entity.id}>
            {editing?.id === entity.id ? (
              <EntityForm
                initial={editing}
                entityTypes={entityTypes}
                onSave={(form) => update.mutate({ id: entity.id, ...form })}
                onCancel={() => setEditing(null)}
                isPending={update.isPending}
              />
            ) : (
              <div className="card hover:shadow-md transition-shadow">
                <div className="flex items-start justify-between mb-2">
                  <div className="flex-1 min-w-0">
                    <h3 className="font-semibold text-gray-900 truncate">{entity.name}</h3>
                    <p className="text-xs text-gray-400 mt-0.5">{entity.entity_type_name}</p>
                  </div>
                  <span className={`badge ml-2 shrink-0 ${entity.active ? 'badge-positive' : 'badge-neutral'}`}>
                    {entity.active ? 'Activa' : 'Inactiva'}
                  </span>
                </div>
                {entity.description && (
                  <p className="text-sm text-gray-600 truncate mb-3">{entity.description}</p>
                )}
                <div className="flex items-center gap-2 mt-3">
                  <Link to={`/entities/${entity.id}`} className="btn-secondary text-xs py-1 px-3">
                    <Eye className="w-3.5 h-3.5" /> Ver detalle
                  </Link>
                  {isAnalyst && (
                    <button onClick={() => setEditing(entity)} className="btn-secondary text-xs py-1 px-3">
                      <Pencil className="w-3.5 h-3.5" /> Editar
                    </button>
                  )}
                </div>
              </div>
            )}
          </div>
        ))}
      </div>

      {entities.length === 0 && (
        <div className="text-center text-gray-400 py-16">No hay entidades configuradas</div>
      )}
    </div>
  )
}
