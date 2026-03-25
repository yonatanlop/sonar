import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Plus, Trash2, ToggleLeft, ToggleRight, Settings2 } from 'lucide-react'
import toast from 'react-hot-toast'
import client from '../api/client'
import { useAuthStore } from '../store/authStore'

// ── API helpers ────────────────────────────────────────────────
const fetchRules    = (entityId) =>
  client.get('/alerts/rules', { params: entityId ? { entity_id: entityId } : {} }).then(r => r.data)
const fetchEntities = () =>
  client.get('/entities', { params: { active_only: false } }).then(r => r.data)

// ── Constantes ────────────────────────────────────────────────
const RULE_LABEL = {
  volume_spike:       'Pico de Volumen',
  negative_threshold: 'Umbral Negatividad',
  bot_activity:       'Actividad Bots',
  keyword_critical:   'Keyword Crítica',
  campaign_detected:  'Campaña Detectada',
  hate_speech:        'Discurso de Odio',
}

const RULE_HINT = {
  volume_spike:       'Umbral = multiplicador vs promedio histórico (ej: 3 = 3x el promedio)',
  negative_threshold: 'Umbral = % de menciones negativas (ej: 70 = 70%)',
  bot_activity:       'Umbral = cantidad mínima de cuentas bot activas',
  keyword_critical:   'Umbral = menciones mínimas con keywords de peso crítico (3)',
  campaign_detected:  'Umbral = cuentas coordinadas mínimas detectadas',
  hate_speech:        'Umbral = menciones mínimas con discurso de odio',
}

const SEV_COLOR = {
  low:      'badge-low',
  medium:   'badge-medium',
  high:     'badge-high',
  critical: 'badge-critical',
}

const EMPTY_FORM = {
  entity_id:      '',
  name:           '',
  rule_type:      'volume_spike',
  threshold:      3,
  window_minutes: 60,
  severity:       'medium',
}

export default function AlertRules() {
  const qc        = useQueryClient()
  const isAnalyst = useAuthStore(s => s.isAnalyst())

  const [filterEntity, setFilterEntity] = useState('')
  const [showForm, setShowForm]         = useState(false)
  const [form, setForm]                 = useState(EMPTY_FORM)

  // ── Queries ──
  const { data: rules    = [], isLoading } = useQuery({
    queryKey: ['rules-all', filterEntity],
    queryFn: () => fetchRules(filterEntity || undefined),
  })

  const { data: entities = [] } = useQuery({
    queryKey: ['entities-all'],
    queryFn: fetchEntities,
  })

  // ── Mutations ──
  const createRule = useMutation({
    mutationFn: () => client.post('/alerts/rules', {
      ...form,
      entity_id:  form.entity_id || undefined,
      threshold:  Number(form.threshold),
      window_minutes: Number(form.window_minutes),
    }),
    onSuccess: () => {
      toast.success('Regla creada')
      qc.invalidateQueries({ queryKey: ['rules-all'] })
      setForm(EMPTY_FORM)
      setShowForm(false)
    },
    onError: (err) => toast.error(err?.response?.data?.detail ?? 'Error al crear regla'),
  })

  const toggleRule = useMutation({
    mutationFn: (id) => client.patch(`/alerts/rules/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['rules-all'] }),
  })

  const deleteRule = useMutation({
    mutationFn: (id) => client.delete(`/alerts/rules/${id}`),
    onSuccess: () => {
      toast.success('Regla eliminada')
      qc.invalidateQueries({ queryKey: ['rules-all'] })
    },
  })

  // Mapa rápido entity_id → nombre
  const entityMap = Object.fromEntries(entities.map(e => [e.id, e.name]))

  return (
    <div className="space-y-6">

      {/* Encabezado */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Reglas de alerta</h1>
          <p className="text-gray-500 text-sm mt-0.5">
            Configura cuándo y cómo se disparan las alertas automáticas
          </p>
        </div>
        {isAnalyst && (
          <button onClick={() => setShowForm(v => !v)} className="btn-primary">
            <Plus className="w-4 h-4" /> Nueva regla
          </button>
        )}
      </div>

      {/* Formulario */}
      {showForm && isAnalyst && (
        <div className="card border-2 border-primary-200 space-y-4">
          <h2 className="font-semibold text-gray-800">Nueva regla de alerta</h2>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="label">Nombre *</label>
              <input className="input" placeholder="Nombre descriptivo"
                value={form.name}
                onChange={e => setForm(f => ({ ...f, name: e.target.value }))} />
            </div>
            <div>
              <label className="label">Entidad</label>
              <select className="input" value={form.entity_id}
                onChange={e => setForm(f => ({ ...f, entity_id: e.target.value }))}>
                <option value="">— Global (todas las entidades) —</option>
                {entities.map(e => <option key={e.id} value={e.id}>{e.name}</option>)}
              </select>
            </div>
            <div>
              <label className="label">Tipo de regla</label>
              <select className="input" value={form.rule_type}
                onChange={e => setForm(f => ({ ...f, rule_type: e.target.value }))}>
                {Object.entries(RULE_LABEL).map(([v, l]) =>
                  <option key={v} value={v}>{l}</option>)}
              </select>
              <p className="text-xs text-gray-400 mt-1">{RULE_HINT[form.rule_type]}</p>
            </div>
            <div>
              <label className="label">Umbral *</label>
              <input type="number" className="input" min={1}
                value={form.threshold}
                onChange={e => setForm(f => ({ ...f, threshold: e.target.value }))} />
            </div>
            <div>
              <label className="label">Ventana de evaluación</label>
              <select className="input" value={form.window_minutes}
                onChange={e => setForm(f => ({ ...f, window_minutes: e.target.value }))}>
                <option value={15}>15 minutos</option>
                <option value={30}>30 minutos</option>
                <option value={60}>1 hora</option>
                <option value={120}>2 horas</option>
                <option value={360}>6 horas</option>
                <option value={1440}>24 horas</option>
              </select>
            </div>
            <div>
              <label className="label">Severidad</label>
              <select className="input" value={form.severity}
                onChange={e => setForm(f => ({ ...f, severity: e.target.value }))}>
                <option value="low">Baja — solo dashboard</option>
                <option value="medium">Media — Telegram + dashboard</option>
                <option value="high">Alta — Todos los canales</option>
                <option value="critical">Crítica — Todos los canales</option>
              </select>
            </div>
          </div>

          <div className="flex gap-2">
            <button
              onClick={() => createRule.mutate()}
              disabled={createRule.isPending || !form.name}
              className="btn-primary text-sm">
              {createRule.isPending ? 'Guardando...' : 'Crear regla'}
            </button>
            <button onClick={() => { setShowForm(false); setForm(EMPTY_FORM) }} className="btn-secondary text-sm">
              Cancelar
            </button>
          </div>
        </div>
      )}

      {/* Filtro por entidad */}
      <div className="flex items-center gap-3">
        <Settings2 className="w-4 h-4 text-gray-400 shrink-0" />
        <select className="input max-w-xs" value={filterEntity}
          onChange={e => setFilterEntity(e.target.value)}>
          <option value="">Todas las entidades</option>
          {entities.map(e => <option key={e.id} value={e.id}>{e.name}</option>)}
        </select>
        <span className="text-sm text-gray-400">{rules.length} regla{rules.length !== 1 ? 's' : ''}</span>
      </div>

      {/* Lista de reglas */}
      {isLoading ? (
        <div className="text-center text-gray-400 py-12">Cargando reglas...</div>
      ) : rules.length === 0 ? (
        <div className="card text-center py-12 text-gray-400">
          <Settings2 className="w-10 h-10 mx-auto mb-3 opacity-30" />
          <p>No hay reglas configuradas</p>
          {isAnalyst && (
            <p className="text-sm mt-1">Crea la primera regla con el botón &quot;Nueva regla&quot;</p>
          )}
        </div>
      ) : (
        <div className="space-y-3">
          {rules.map(rule => (
            <div
              key={rule.id}
              className={`card flex items-start gap-4 transition-opacity ${!rule.active ? 'opacity-50' : ''}`}
            >
              {/* Indicador de severidad */}
              <div className={`w-1 self-stretch rounded-full shrink-0 ${
                rule.severity === 'critical' ? 'bg-critical' :
                rule.severity === 'high'     ? 'bg-high'     :
                rule.severity === 'medium'   ? 'bg-medium'   :
                                               'bg-low'
              }`} />

              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="font-semibold text-gray-900">{rule.name}</span>
                  <span className={`badge ${SEV_COLOR[rule.severity]}`}>{rule.severity.toUpperCase()}</span>
                  <span className="badge bg-gray-100 text-gray-600">{RULE_LABEL[rule.rule_type]}</span>
                  {!rule.active && (
                    <span className="badge bg-gray-100 text-gray-400">Inactiva</span>
                  )}
                </div>

                <div className="mt-1.5 flex flex-wrap gap-x-4 gap-y-1 text-xs text-gray-500">
                  <span>
                    Entidad: <span className="font-medium text-gray-700">
                      {rule.entity_id ? (entityMap[rule.entity_id] ?? rule.entity_id.slice(0, 8)) : 'Global'}
                    </span>
                  </span>
                  <span>Umbral: <span className="font-medium text-gray-700">{rule.threshold}</span></span>
                  <span>Ventana: <span className="font-medium text-gray-700">{rule.window_minutes} min</span></span>
                </div>

                <p className="text-xs text-gray-400 mt-1">{RULE_HINT[rule.rule_type]}</p>
              </div>

              {isAnalyst && (
                <div className="flex items-center gap-2 shrink-0">
                  <button
                    onClick={() => toggleRule.mutate(rule.id)}
                    title={rule.active ? 'Desactivar' : 'Activar'}
                    className="text-gray-400 hover:text-primary-600 transition-colors">
                    {rule.active
                      ? <ToggleRight className="w-5 h-5 text-green-500" />
                      : <ToggleLeft className="w-5 h-5" />}
                  </button>
                  <button
                    onClick={() => deleteRule.mutate(rule.id)}
                    title="Eliminar regla"
                    className="text-gray-300 hover:text-red-500 transition-colors">
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
