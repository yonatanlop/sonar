import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Plus, Pencil, Trash2 } from 'lucide-react'
import toast from 'react-hot-toast'
import client from '../../../shared/api/client'

const fetchRules    = () => client.get('/alert-rules').then(r => r.data)
const fetchEntities = () => client.get('/entities').then(r => r.data)

const RULE_TYPES = [
  'volume_spike','negative_threshold','bot_activity','keyword_critical','hate_speech','anomaly_detected',
]
const SEVERITIES = ['low','medium','high','critical']

function RuleForm({ initial, entities, onSave, onCancel, isPending }) {
  const [form, setForm] = useState(initial ?? {
    name: '', rule_type: 'volume_spike', entity_id: '', threshold: 10,
    window_minutes: 60, severity: 'medium', active: true,
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
          <label className="label">Tipo de regla</label>
          <select className="input" value={form.rule_type} onChange={e => set('rule_type', e.target.value)}>
            {RULE_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
          </select>
        </div>
        <div>
          <label className="label">Entidad (opcional)</label>
          <select className="input" value={form.entity_id} onChange={e => set('entity_id', e.target.value)}>
            <option value="">Todas las entidades</option>
            {entities?.map(e => <option key={e.id} value={e.id}>{e.name}</option>)}
          </select>
        </div>
        <div>
          <label className="label">Umbral</label>
          <input className="input" type="number" min={1} value={form.threshold}
            onChange={e => set('threshold', Number(e.target.value))} />
        </div>
        <div>
          <label className="label">Ventana (minutos)</label>
          <input className="input" type="number" min={5} value={form.window_minutes}
            onChange={e => set('window_minutes', Number(e.target.value))} />
        </div>
        <div>
          <label className="label">Severidad</label>
          <select className="input" value={form.severity} onChange={e => set('severity', e.target.value)}>
            {SEVERITIES.map(s => <option key={s} value={s}>{s}</option>)}
          </select>
        </div>
      </div>
      <div className="flex gap-2">
        <button type="submit" className="btn-primary" disabled={isPending}>
          {isPending ? 'Guardando...' : initial ? 'Actualizar' : 'Crear regla'}
        </button>
        <button type="button" className="btn-secondary" onClick={onCancel}>Cancelar</button>
      </div>
    </form>
  )
}

export default function AlertRules() {
  const qc = useQueryClient()
  const [showForm, setShowForm] = useState(false)
  const [editing, setEditing]   = useState(null)

  const { data: rules = [], isLoading }  = useQuery({ queryKey: ['alert-rules'], queryFn: fetchRules })
  const { data: entities = [] }          = useQuery({ queryKey: ['entities'], queryFn: fetchEntities })

  const create = useMutation({
    mutationFn: (body) => client.post('/alert-rules', body),
    onSuccess: () => { toast.success('Regla creada'); qc.invalidateQueries({ queryKey: ['alert-rules'] }); setShowForm(false) },
    onError: (e) => toast.error(e?.response?.data?.detail ?? 'Error'),
  })

  const update = useMutation({
    mutationFn: ({ id, ...body }) => client.patch(`/alert-rules/${id}`, body),
    onSuccess: () => { toast.success('Regla actualizada'); qc.invalidateQueries({ queryKey: ['alert-rules'] }); setEditing(null) },
    onError: (e) => toast.error(e?.response?.data?.detail ?? 'Error'),
  })

  const remove = useMutation({
    mutationFn: (id) => client.delete(`/alert-rules/${id}`),
    onSuccess: () => { toast.success('Regla eliminada'); qc.invalidateQueries({ queryKey: ['alert-rules'] }) },
  })

  if (isLoading) return <div className="text-center text-gray-400 py-12">Cargando...</div>

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Reglas de alerta</h1>
        {!showForm && (
          <button className="btn-primary" onClick={() => setShowForm(true)}>
            <Plus className="w-4 h-4" /> Nueva regla
          </button>
        )}
      </div>

      {showForm && (
        <RuleForm
          entities={entities}
          onSave={(form) => create.mutate(form)}
          onCancel={() => setShowForm(false)}
          isPending={create.isPending}
        />
      )}

      <div className="card p-0 overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b border-gray-100">
            <tr>
              {['Nombre','Tipo','Entidad','Umbral','Ventana','Severidad','Estado',''].map(h => (
                <th key={h} className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-50">
            {rules.map(rule => (
              <tr key={rule.id}>
                {editing?.id === rule.id ? (
                  <td colSpan={8} className="px-4 py-3">
                    <RuleForm
                      initial={editing}
                      entities={entities}
                      onSave={(form) => update.mutate({ id: rule.id, ...form })}
                      onCancel={() => setEditing(null)}
                      isPending={update.isPending}
                    />
                  </td>
                ) : (
                  <>
                    <td className="px-4 py-3 font-medium text-gray-900">{rule.name}</td>
                    <td className="px-4 py-3 text-gray-600 text-xs">{rule.rule_type}</td>
                    <td className="px-4 py-3 text-gray-500 text-xs truncate max-w-32">{rule.entity_name ?? 'Global'}</td>
                    <td className="px-4 py-3 text-gray-600">{rule.threshold}</td>
                    <td className="px-4 py-3 text-gray-600">{rule.window_minutes}m</td>
                    <td className="px-4 py-3">
                      <span className={`badge badge-${rule.severity}`}>{rule.severity}</span>
                    </td>
                    <td className="px-4 py-3">
                      <span className={`badge ${rule.active ? 'badge-positive' : 'badge-neutral'}`}>
                        {rule.active ? 'Activa' : 'Inactiva'}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex gap-2">
                        <button onClick={() => setEditing(rule)} className="text-gray-400 hover:text-primary-600">
                          <Pencil className="w-4 h-4" />
                        </button>
                        <button onClick={() => remove.mutate(rule.id)} className="text-gray-400 hover:text-red-600">
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    </td>
                  </>
                )}
              </tr>
            ))}
          </tbody>
        </table>
        {rules.length === 0 && (
          <p className="text-center text-gray-400 py-8">No hay reglas configuradas</p>
        )}
      </div>
    </div>
  )
}
