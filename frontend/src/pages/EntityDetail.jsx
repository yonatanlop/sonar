import { useState } from 'react'
import { useParams, Link, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import ReactECharts from 'echarts-for-react'
import {
  ArrowLeft, Building2, Tag, AtSign, Plus, Trash2,
  ToggleLeft, ToggleRight, AlertTriangle,
} from 'lucide-react'
import toast from 'react-hot-toast'
import client from '../api/client'
import { useAuthStore } from '../store/authStore'

// ── API helpers ────────────────────────────────────────────────
const fetchEntity  = (id) => client.get(`/entities/${id}`).then(r => r.data)
const fetchRules   = (id) => client.get('/alerts/rules', { params: { entity_id: id } }).then(r => r.data)

// ── Constantes ────────────────────────────────────────────────
const WEIGHT_LABEL = { 1: 'Normal', 2: 'Importante', 3: 'Crítico' }
const WEIGHT_COLOR = { 1: 'badge-low', 2: 'badge-medium', 3: 'badge-critical' }
const RULE_LABEL   = {
  volume_spike:       'Pico de Volumen',
  negative_threshold: 'Umbral Negatividad',
  bot_activity:       'Actividad Bots',
  keyword_critical:   'Keyword Crítica',
  campaign_detected:  'Campaña Detectada',
  hate_speech:        'Discurso de Odio',
}
const SEV_COLOR = {
  low:      'badge-low',
  medium:   'badge-medium',
  high:     'badge-high',
  critical: 'badge-critical',
}
const RISK_COLOR = { alto: 'text-red-600', medio: 'text-yellow-600', bajo: 'text-green-600' }

// ── Componente principal ───────────────────────────────────────
export default function EntityDetail() {
  const { id }    = useParams()
  const navigate  = useNavigate()
  const qc        = useQueryClient()
  const isAnalyst = useAuthStore(s => s.isAnalyst())

  const [tab, setTab] = useState('overview')  // overview | keywords | aliases | rules

  // ── Formularios ──
  const [kwForm,    setKwForm]    = useState({ keyword: '', language: 'es', weight: 1 })
  const [aliasForm, setAliasForm] = useState('')
  const [ruleForm,  setRuleForm]  = useState({
    name: '', rule_type: 'volume_spike', threshold: 3,
    window_minutes: 60, severity: 'medium',
  })

  // ── Queries ──
  const { data: entity, isLoading } = useQuery({
    queryKey: ['entity', id],
    queryFn: () => fetchEntity(id),
  })

  const { data: rules = [] } = useQuery({
    queryKey: ['rules', id],
    queryFn: () => fetchRules(id),
    enabled: tab === 'rules',
  })

  // ── Mutations: keywords ──
  const addKw = useMutation({
    mutationFn: () => client.post(`/entities/${id}/keywords`, kwForm),
    onSuccess: () => {
      toast.success('Keyword agregada')
      qc.invalidateQueries({ queryKey: ['entity', id] })
      setKwForm({ keyword: '', language: 'es', weight: 1 })
    },
  })
  const delKw = useMutation({
    mutationFn: (kwId) => client.delete(`/entities/${id}/keywords/${kwId}`),
    onSuccess: () => {
      toast.success('Keyword eliminada')
      qc.invalidateQueries({ queryKey: ['entity', id] })
    },
  })

  // ── Mutations: aliases ──
  const addAlias = useMutation({
    mutationFn: () => client.post(`/entities/${id}/aliases`, { alias: aliasForm }),
    onSuccess: () => {
      toast.success('Alias agregado')
      qc.invalidateQueries({ queryKey: ['entity', id] })
      setAliasForm('')
    },
  })
  const delAlias = useMutation({
    mutationFn: (aid) => client.delete(`/entities/${id}/aliases/${aid}`),
    onSuccess: () => {
      toast.success('Alias eliminado')
      qc.invalidateQueries({ queryKey: ['entity', id] })
    },
  })

  // ── Mutations: reglas ──
  const addRule = useMutation({
    mutationFn: () => client.post('/alerts/rules', { ...ruleForm, entity_id: id }),
    onSuccess: () => {
      toast.success('Regla creada')
      qc.invalidateQueries({ queryKey: ['rules', id] })
      setRuleForm({ name: '', rule_type: 'volume_spike', threshold: 3, window_minutes: 60, severity: 'medium' })
    },
  })
  const toggleRule = useMutation({
    mutationFn: (ruleId) => client.patch(`/alerts/rules/${ruleId}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['rules', id] }),
  })
  const delRule = useMutation({
    mutationFn: (ruleId) => client.delete(`/alerts/rules/${ruleId}`),
    onSuccess: () => {
      toast.success('Regla eliminada')
      qc.invalidateQueries({ queryKey: ['rules', id] })
    },
  })

  // ── Toggle entidad activa ──
  const toggleEntity = useMutation({
    mutationFn: () => client.patch(`/entities/${id}`, { active: !entity.active }),
    onSuccess: () => {
      toast.success(entity.active ? 'Entidad pausada' : 'Entidad activada')
      qc.invalidateQueries({ queryKey: ['entity', id] })
      qc.invalidateQueries({ queryKey: ['entities'] })
    },
  })

  if (isLoading) return <div className="text-center text-gray-400 py-20">Cargando...</div>
  if (!entity)   return <div className="text-center text-red-500 py-20">Entidad no encontrada</div>

  // ── Gráfica sentimiento (dona) ──
  const snt     = entity.stats_7d?.sentiment ?? {}
  const pieData = [
    { value: snt.very_negative ?? 0, name: 'Muy negativo', itemStyle: { color: '#dc2626' } },
    { value: snt.negative      ?? 0, name: 'Negativo',     itemStyle: { color: '#f97316' } },
    { value: snt.neutral       ?? 0, name: 'Neutro',       itemStyle: { color: '#d1d5db' } },
    { value: snt.positive      ?? 0, name: 'Positivo',     itemStyle: { color: '#4ade80' } },
    { value: snt.very_positive ?? 0, name: 'Muy positivo', itemStyle: { color: '#16a34a' } },
  ].filter(d => d.value > 0)

  const pieOption = {
    tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
    legend: { bottom: 0, textStyle: { fontSize: 11 } },
    series: [{
      type: 'pie', radius: ['40%', '70%'],
      label: { show: false },
      data: pieData.length ? pieData : [{ value: 1, name: 'Sin datos', itemStyle: { color: '#e5e7eb' } }],
    }],
  }

  const TABS = [
    { key: 'overview',  label: 'Resumen' },
    { key: 'keywords',  label: `Keywords (${entity.keywords?.length ?? 0})` },
    { key: 'aliases',   label: `Aliases (${entity.aliases?.length ?? 0})` },
    { key: 'rules',     label: 'Reglas de alerta' },
  ]

  return (
    <div className="space-y-6">

      {/* Encabezado */}
      <div className="flex items-center gap-3">
        <button onClick={() => navigate('/entities')}
          className="p-2 rounded-lg hover:bg-gray-100 text-gray-500">
          <ArrowLeft className="w-5 h-5" />
        </button>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-3 flex-wrap">
            <h1 className="text-2xl font-bold text-gray-900 truncate">{entity.name}</h1>
            {entity.risk_level && (
              <span className={`text-sm font-semibold ${RISK_COLOR[entity.risk_level]}`}>
                ● {entity.risk_level.toUpperCase()}
              </span>
            )}
            <span className={`badge ${entity.active ? 'badge-low' : 'bg-gray-100 text-gray-500'}`}>
              {entity.active ? 'Activa' : 'Pausada'}
            </span>
          </div>
          <p className="text-sm text-gray-500 mt-0.5">
            {entity.type_name} · {entity.country_code ?? '—'}
            {entity.description && ` · ${entity.description}`}
          </p>
        </div>
        {isAnalyst && (
          <button onClick={() => toggleEntity.mutate()}
            disabled={toggleEntity.isPending}
            className="btn-secondary text-sm">
            {entity.active ? <ToggleRight className="w-4 h-4 text-green-500" /> : <ToggleLeft className="w-4 h-4" />}
            {entity.active ? 'Pausar' : 'Activar'}
          </button>
        )}
      </div>

      {/* Tabs */}
      <div className="border-b border-gray-200">
        <nav className="-mb-px flex gap-1">
          {TABS.map(t => (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${
                tab === t.key
                  ? 'border-primary-600 text-primary-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700'
              }`}
            >
              {t.label}
            </button>
          ))}
        </nav>
      </div>

      {/* ── Resumen ── */}
      {tab === 'overview' && (
        <div className="space-y-6">
          {/* Métricas */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {[
              { label: 'Menciones hoy',      value: entity.mention_count ?? 0 },
              { label: 'Total 7 días',        value: entity.stats_7d?.total ?? 0 },
              { label: '% Negativas 7d',      value: `${entity.stats_7d?.negative_pct ?? 0}%` },
              { label: 'Keywords activas',    value: entity.keywords?.filter(k => k.active).length ?? 0 },
            ].map(m => (
              <div key={m.label} className="card text-center">
                <p className="text-2xl font-bold text-gray-900">{m.value}</p>
                <p className="text-xs text-gray-500 mt-1">{m.label}</p>
              </div>
            ))}
          </div>

          {/* Gráfica sentimiento */}
          <div className="card">
            <h2 className="text-sm font-semibold text-gray-700 mb-4">Distribución de sentimiento — últimos 7 días</h2>
            {entity.stats_7d?.total > 0 ? (
              <ReactECharts option={pieOption} style={{ height: 260 }} />
            ) : (
              <div className="text-center text-gray-400 py-12 text-sm">
                Sin menciones procesadas en los últimos 7 días
              </div>
            )}
          </div>

          {/* Accesos rápidos */}
          <div className="flex flex-wrap gap-3">
            <Link
              to={`/mentions?entity_id=${entity.id}`}
              className="btn-secondary text-sm"
            >
              <Building2 className="w-4 h-4" /> Ver menciones
            </Link>
            <Link
              to={`/alerts?entity_id=${entity.id}`}
              className="btn-secondary text-sm"
            >
              <AlertTriangle className="w-4 h-4" /> Ver alertas
            </Link>
          </div>
        </div>
      )}

      {/* ── Keywords ── */}
      {tab === 'keywords' && (
        <div className="space-y-4">
          {isAnalyst && (
            <div className="card border-primary-200 border">
              <h2 className="font-semibold mb-4 text-sm">Nueva keyword</h2>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <div className="sm:col-span-1">
                  <label className="label">Keyword *</label>
                  <input className="input" placeholder="Ej: corrupción"
                    value={kwForm.keyword}
                    onChange={e => setKwForm(f => ({ ...f, keyword: e.target.value }))} />
                </div>
                <div>
                  <label className="label">Idioma</label>
                  <select className="input" value={kwForm.language}
                    onChange={e => setKwForm(f => ({ ...f, language: e.target.value }))}>
                    <option value="es">Español</option>
                    <option value="en">Inglés</option>
                    <option value="pt">Portugués</option>
                  </select>
                </div>
                <div>
                  <label className="label">Peso</label>
                  <select className="input" value={kwForm.weight}
                    onChange={e => setKwForm(f => ({ ...f, weight: parseInt(e.target.value) }))}>
                    <option value={1}>1 — Normal</option>
                    <option value={2}>2 — Importante</option>
                    <option value={3}>3 — Crítico</option>
                  </select>
                </div>
              </div>
              <button
                onClick={() => addKw.mutate()}
                disabled={addKw.isPending || !kwForm.keyword}
                className="btn-primary mt-3 text-sm">
                <Plus className="w-4 h-4" />
                {addKw.isPending ? 'Guardando...' : 'Agregar keyword'}
              </button>
            </div>
          )}

          <div className="card">
            {entity.keywords?.length === 0 ? (
              <p className="text-gray-400 text-sm text-center py-6">No hay keywords definidas</p>
            ) : (
              <div className="divide-y divide-gray-100">
                {entity.keywords.map(kw => (
                  <div key={kw.id} className="flex items-center gap-3 py-3">
                    <Tag className="w-4 h-4 text-gray-400 shrink-0" />
                    <span className="flex-1 text-sm font-medium text-gray-800">{kw.keyword}</span>
                    <span className="text-xs text-gray-400">{kw.language.toUpperCase()}</span>
                    <span className={`badge ${WEIGHT_COLOR[kw.weight]}`}>
                      {WEIGHT_LABEL[kw.weight]}
                    </span>
                    {isAnalyst && (
                      <button onClick={() => delKw.mutate(kw.id)}
                        className="text-gray-300 hover:text-red-500 transition-colors ml-1">
                        <Trash2 className="w-4 h-4" />
                      </button>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* ── Aliases ── */}
      {tab === 'aliases' && (
        <div className="space-y-4">
          {isAnalyst && (
            <div className="card border-primary-200 border">
              <h2 className="font-semibold mb-4 text-sm">Nuevo alias</h2>
              <div className="flex gap-3">
                <input className="input flex-1" placeholder="Ej: @nombre_usuario, nombre alternativo"
                  value={aliasForm}
                  onChange={e => setAliasForm(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && aliasForm && addAlias.mutate()} />
                <button onClick={() => addAlias.mutate()}
                  disabled={addAlias.isPending || !aliasForm}
                  className="btn-primary text-sm">
                  <Plus className="w-4 h-4" />
                  {addAlias.isPending ? 'Guardando...' : 'Agregar'}
                </button>
              </div>
            </div>
          )}

          <div className="card">
            {entity.aliases?.length === 0 ? (
              <p className="text-gray-400 text-sm text-center py-6">No hay aliases definidos</p>
            ) : (
              <div className="divide-y divide-gray-100">
                {entity.aliases.map(a => (
                  <div key={a.id} className="flex items-center gap-3 py-3">
                    <AtSign className="w-4 h-4 text-gray-400 shrink-0" />
                    <span className="flex-1 text-sm text-gray-800">{a.alias}</span>
                    {isAnalyst && (
                      <button onClick={() => delAlias.mutate(a.id)}
                        className="text-gray-300 hover:text-red-500 transition-colors">
                        <Trash2 className="w-4 h-4" />
                      </button>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* ── Reglas de alerta ── */}
      {tab === 'rules' && (
        <div className="space-y-4">
          {isAnalyst && (
            <div className="card border-primary-200 border">
              <h2 className="font-semibold mb-4 text-sm">Nueva regla de alerta</h2>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="label">Nombre *</label>
                  <input className="input" placeholder="Nombre descriptivo"
                    value={ruleForm.name}
                    onChange={e => setRuleForm(f => ({ ...f, name: e.target.value }))} />
                </div>
                <div>
                  <label className="label">Tipo de regla</label>
                  <select className="input" value={ruleForm.rule_type}
                    onChange={e => setRuleForm(f => ({ ...f, rule_type: e.target.value }))}>
                    {Object.entries(RULE_LABEL).map(([v, l]) =>
                      <option key={v} value={v}>{l}</option>)}
                  </select>
                </div>
                <div>
                  <label className="label">Umbral</label>
                  <input type="number" className="input" min={1}
                    value={ruleForm.threshold}
                    onChange={e => setRuleForm(f => ({ ...f, threshold: parseInt(e.target.value) }))} />
                </div>
                <div>
                  <label className="label">Ventana (minutos)</label>
                  <select className="input" value={ruleForm.window_minutes}
                    onChange={e => setRuleForm(f => ({ ...f, window_minutes: parseInt(e.target.value) }))}>
                    <option value={30}>30 min</option>
                    <option value={60}>1 hora</option>
                    <option value={120}>2 horas</option>
                    <option value={360}>6 horas</option>
                    <option value={1440}>24 horas</option>
                  </select>
                </div>
                <div>
                  <label className="label">Severidad</label>
                  <select className="input" value={ruleForm.severity}
                    onChange={e => setRuleForm(f => ({ ...f, severity: e.target.value }))}>
                    <option value="low">Baja</option>
                    <option value="medium">Media</option>
                    <option value="high">Alta</option>
                    <option value="critical">Crítica</option>
                  </select>
                </div>
              </div>
              <button
                onClick={() => addRule.mutate()}
                disabled={addRule.isPending || !ruleForm.name}
                className="btn-primary mt-3 text-sm">
                <Plus className="w-4 h-4" />
                {addRule.isPending ? 'Guardando...' : 'Crear regla'}
              </button>
            </div>
          )}

          <div className="card">
            {rules.length === 0 ? (
              <p className="text-gray-400 text-sm text-center py-6">No hay reglas configuradas para esta entidad</p>
            ) : (
              <div className="divide-y divide-gray-100">
                {rules.map(rule => (
                  <div key={rule.id} className={`py-3 flex items-start gap-3 ${!rule.active ? 'opacity-50' : ''}`}>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-sm font-semibold text-gray-800">{rule.name}</span>
                        <span className={`badge ${SEV_COLOR[rule.severity]}`}>{rule.severity}</span>
                        <span className="badge bg-gray-100 text-gray-600">{RULE_LABEL[rule.rule_type]}</span>
                      </div>
                      <p className="text-xs text-gray-400 mt-1">
                        Umbral: {rule.threshold} · Ventana: {rule.window_minutes} min
                      </p>
                    </div>
                    {isAnalyst && (
                      <div className="flex gap-2 shrink-0">
                        <button onClick={() => toggleRule.mutate(rule.id)}
                          className="text-gray-400 hover:text-primary-600 transition-colors">
                          {rule.active
                            ? <ToggleRight className="w-5 h-5 text-green-500" />
                            : <ToggleLeft className="w-5 h-5" />}
                        </button>
                        <button onClick={() => delRule.mutate(rule.id)}
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
        </div>
      )}
    </div>
  )
}
