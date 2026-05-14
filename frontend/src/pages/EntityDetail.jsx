import { useState } from 'react'
import { useParams, Link, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import ReactECharts from 'echarts-for-react'
import {
  ArrowLeft, Building2, Tag, AtSign, Plus, Trash2,
  ToggleLeft, ToggleRight, AlertTriangle, TrendingUp, Sparkles, RefreshCw, Hash, Camera,
} from 'lucide-react'
import { format } from 'date-fns'
import { es } from 'date-fns/locale'
import toast from 'react-hot-toast'
import client from '../api/client'
import { useAuthStore } from '../store/authStore'

// ── API helpers ────────────────────────────────────────────────
const fetchEntity          = (id) => client.get(`/entities/${id}`).then(r => r.data)
const fetchRules           = (id) => client.get('/alerts/rules', { params: { entity_id: id } }).then(r => r.data)
const fetchAnomalies       = (id) => client.get(`/entities/${id}/anomalies`, { params: { days: 7 } }).then(r => r.data)
const fetchSummaries       = (id) => client.get(`/entities/${id}/summaries`, { params: { limit: 1 } }).then(r => r.data)
const fetchTopics          = (id) => client.get(`/entities/${id}/topics`,    { params: { days: 7 } }).then(r => r.data)
const fetchForecast        = (id) => client.get(`/entities/${id}/forecast`,  { params: { history_days: 14 } }).then(r => r.data)
const fetchRelatedEntities = (id) => client.get(`/entities/${id}/related-entities`,   { params: { days: 30, limit: 20 } }).then(r => r.data)
const fetchKwSuggestions   = (id) => client.get(`/entities/${id}/keyword-suggestions`, { params: { days: 30 } }).then(r => r.data)
const fetchFaceRefs        = (id) => client.get(`/entities/${id}/face-references`).then(r => r.data)
const fetchInfluencers     = (id, days) => client.get(`/entities/${id}/influencers`, { params: { days, limit: 10 } }).then(r => r.data)

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

  const [tab, setTab]           = useState('overview')  // overview | keywords | aliases | rules | faces | influencers
  const [influDays, setInfluDays] = useState(7)

  // ── Formularios ──
  const [kwForm,    setKwForm]    = useState({ keyword: '', keyword_secondary: '', logic_op: 'AND', language: 'es', weight: 1 })
  const [aliasForm, setAliasForm] = useState('')
  const [faceForm,  setFaceForm]  = useState({ person_name: '', photo_url: '' })
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

  const { data: anomaliesData } = useQuery({
    queryKey: ['anomalies', id],
    queryFn: () => fetchAnomalies(id),
    enabled: tab === 'overview',
    refetchInterval: 5 * 60 * 1000,
  })

  const { data: topicsData } = useQuery({
    queryKey: ['topics', id],
    queryFn: () => fetchTopics(id),
    enabled: tab === 'overview',
    refetchInterval: 60 * 60 * 1000,  // refrescar cada hora
  })

  const triggerTopics = useMutation({
    mutationFn: () => client.post(`/entities/${id}/topics/analyze`),
    onSuccess: () => {
      toast.success('Análisis de temas completado')
      qc.invalidateQueries({ queryKey: ['topics', id] })
    },
    onError: (err) => toast.error(err?.response?.data?.detail ?? 'Error en análisis de temas'),
  })

  const { data: summaryData, isLoading: summaryLoading } = useQuery({
    queryKey: ['summaries', id],
    queryFn: () => fetchSummaries(id),
    enabled: tab === 'overview',
  })

  const { data: forecastData } = useQuery({
    queryKey: ['forecast', id],
    queryFn: () => fetchForecast(id),
    enabled: tab === 'overview',
    staleTime: 30 * 60 * 1000,
  })

  const { data: relatedData } = useQuery({
    queryKey: ['related-entities', id],
    queryFn: () => fetchRelatedEntities(id),
    enabled: tab === 'overview',
    staleTime: 60 * 60 * 1000,
  })

  const { data: kwSuggestions, refetch: refetchSuggestions } = useQuery({
    queryKey: ['kw-suggestions', id],
    queryFn: () => fetchKwSuggestions(id),
    enabled: tab === 'overview',
    staleTime: 30 * 60 * 1000,
  })

  const quickAddKw = useMutation({
    mutationFn: (keyword) => client.post(`/entities/${id}/keywords`, { keyword, language: 'es', weight: 1 }),
    onSuccess: (_, keyword) => {
      toast.success(`Keyword "${keyword}" agregada`)
      qc.invalidateQueries({ queryKey: ['entity', id] })
      qc.invalidateQueries({ queryKey: ['kw-suggestions', id] })
    },
    onError: (err) => toast.error(err?.response?.data?.detail ?? 'Error al agregar keyword'),
  })

  const triggerSummary = useMutation({
    mutationFn: () => client.post(`/entities/${id}/summaries/generate`),
    onSuccess: () => {
      toast.success('Resumen generado')
      qc.invalidateQueries({ queryKey: ['summaries', id] })
    },
    onError: (err) => toast.error(err?.response?.data?.detail ?? 'Error al generar resumen'),
  })

  // ── Mutations: keywords ──
  const addKw = useMutation({
    mutationFn: () => client.post(`/entities/${id}/keywords`, {
      ...kwForm,
      keyword_secondary: kwForm.keyword_secondary || null,
      logic_op: kwForm.logic_op,
    }),
    onSuccess: () => {
      toast.success('Keyword agregada')
      qc.invalidateQueries({ queryKey: ['entity', id] })
      setKwForm({ keyword: '', keyword_secondary: '', logic_op: 'AND', language: 'es', weight: 1 })
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

  // ── Queries y mutations: fotos de referencia (módulo 7) ──
  const { data: faceRefsData, refetch: refetchFaceRefs } = useQuery({
    queryKey: ['face-refs', id],
    queryFn: () => fetchFaceRefs(id),
    enabled: tab === 'faces',
  })

  const { data: influencersData, isLoading: influLoading } = useQuery({
    queryKey: ['influencers', id, influDays],
    queryFn: () => fetchInfluencers(id, influDays),
    enabled: tab === 'influencers',
  })
  const addFaceRef = useMutation({
    mutationFn: () => client.post(`/entities/${id}/face-references`, faceForm),
    onSuccess: () => {
      toast.success(`Foto de "${faceForm.person_name}" agregada`)
      refetchFaceRefs()
      setFaceForm({ person_name: '', photo_url: '' })
    },
    onError: (err) => toast.error(err?.response?.data?.detail ?? 'Error al agregar foto'),
  })
  const delFaceRef = useMutation({
    mutationFn: (personName) => client.delete(`/entities/${id}/face-references/${encodeURIComponent(personName)}`),
    onSuccess: () => {
      toast.success('Fotos eliminadas')
      refetchFaceRefs()
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

  // ── Gráfica pronóstico (historial sólido + proyección punteada) ──
  const hasForecast = (forecastData?.history?.length > 0) && (forecastData?.forecast?.length > 0)
  const forecastOption = hasForecast ? (() => {
    const histDates = forecastData.history.map(h => h.date.slice(5))   // MM-DD
    const fcDates   = forecastData.forecast.map(f => f.date.slice(5))
    const allDates  = [...histDates, ...fcDates]
    const pad       = (arr, before, after) => [...Array(before).fill(null), ...arr, ...Array(after).fill(null)]
    const hLen = histDates.length, fLen = fcDates.length

    return {
      tooltip: {
        trigger: 'axis',
        formatter: (params) => {
          const lines = params
            .filter(p => p.value != null)
            .map(p => `${p.marker}${p.seriesName}: <b>${typeof p.value === 'number' ? p.value.toFixed(1) : p.value}</b>`)
          return `${params[0]?.axisValue}<br/>${lines.join('<br/>')}`
        },
      },
      legend: { bottom: 0, textStyle: { fontSize: 10 }, data: ['Historial', 'Pronóstico', 'Confianza ±'] },
      grid: { top: 10, bottom: 40, left: 36, right: 16 },
      xAxis: {
        type: 'category',
        data: allDates,
        axisLabel: { fontSize: 10 },
        axisLine: { lineStyle: { color: '#e5e7eb' } },
      },
      yAxis: { type: 'value', axisLabel: { fontSize: 10 }, minInterval: 1 },
      series: [
        {
          name: 'Historial',
          type: 'line',
          data: pad(forecastData.history.map(h => h.count), 0, fLen),
          smooth: true,
          symbol: 'circle',
          symbolSize: 4,
          lineStyle: { color: '#3b82f6', width: 2 },
          itemStyle: { color: '#3b82f6' },
        },
        {
          name: 'Pronóstico',
          type: 'line',
          data: pad(forecastData.forecast.map(f => f.predicted), hLen, 0),
          smooth: true,
          symbol: 'diamond',
          symbolSize: 5,
          lineStyle: { color: '#f59e0b', width: 2, type: 'dashed' },
          itemStyle: { color: '#f59e0b' },
        },
        {
          name: 'Confianza ±',
          type: 'line',
          data: pad(forecastData.forecast.map(f => f.high), hLen, 0),
          lineStyle: { opacity: 0 },
          itemStyle: { opacity: 0 },
          symbol: 'none',
          areaStyle: { color: 'rgba(245,158,11,0.12)', origin: 'start' },
          stack: 'ci',
          legendHoverLink: false,
          tooltip: { show: false },
        },
        {
          name: '',
          type: 'line',
          data: pad(forecastData.forecast.map(f => f.low), hLen, 0),
          lineStyle: { opacity: 0 },
          itemStyle: { opacity: 0 },
          symbol: 'none',
          areaStyle: { color: '#ffffff', origin: 'start' },
          stack: 'ci',
          legendHoverLink: false,
          tooltip: { show: false },
          showInLegend: false,
        },
      ],
    }
  })() : null

  const TABS = [
    { key: 'overview',     label: 'Resumen' },
    { key: 'keywords',     label: `Keywords (${entity.keywords?.length ?? 0})` },
    { key: 'aliases',      label: `Aliases (${entity.aliases?.length ?? 0})` },
    { key: 'rules',        label: 'Reglas de alerta' },
    { key: 'influencers',  label: '⭐ Influencers' },
    { key: 'faces',        label: '📸 Reconocimiento visual' },
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

          {/* Panel de temas (Topic Modeling) */}
          <div className="card">
            <div className="flex items-center gap-2 mb-3">
              <Hash className="w-4 h-4 text-blue-500" />
              <h2 className="text-sm font-semibold text-gray-700">Temas detectados — últimos 7 días</h2>
              {isAnalyst && (
                <button
                  onClick={() => triggerTopics.mutate()}
                  disabled={triggerTopics.isPending}
                  className="ml-auto text-xs text-blue-600 hover:text-blue-800 flex items-center gap-1"
                >
                  <RefreshCw className={`w-3 h-3 ${triggerTopics.isPending ? 'animate-spin' : ''}`} />
                  {triggerTopics.isPending ? 'Analizando...' : 'Analizar ahora'}
                </button>
              )}
            </div>

            {topicsData?.topics?.length > 0 ? (
              <div>
                <p className="text-xs text-gray-400 mb-3">
                  {topicsData.total_labeled} menciones agrupadas en {topicsData.topics.length} temas · IA (TF-IDF)
                </p>
                {/* Nube de temas — píldoras con tamaño proporcional */}
                <div className="flex flex-wrap gap-2">
                  {topicsData.topics.map((t, i) => {
                    // Tamaño de fuente entre 11px y 18px según porcentaje
                    const maxPct = topicsData.topics[0]?.pct ?? 1
                    const fontSize = Math.round(11 + (t.pct / maxPct) * 7)
                    const COLORS = [
                      'bg-blue-100 text-blue-800',
                      'bg-indigo-100 text-indigo-800',
                      'bg-sky-100 text-sky-800',
                      'bg-cyan-100 text-cyan-800',
                      'bg-teal-100 text-teal-800',
                      'bg-violet-100 text-violet-800',
                      'bg-purple-100 text-purple-800',
                      'bg-fuchsia-100 text-fuchsia-800',
                    ]
                    const colorCls = COLORS[i % COLORS.length]
                    return (
                      <span
                        key={t.topic_id}
                        className={`rounded-full px-3 py-1 font-medium cursor-default ${colorCls}`}
                        style={{ fontSize }}
                        title={`${t.count} menciones (${t.pct}%)`}
                      >
                        {t.label}
                        <span className="ml-1 opacity-60 text-xs">({t.count})</span>
                      </span>
                    )
                  })}
                </div>
              </div>
            ) : (
              <div className="text-sm text-gray-400 text-center py-4">
                <p>Los temas se detectan automáticamente cada hora.</p>
                {isAnalyst && (
                  <p className="mt-1 text-xs">
                    Necesita mínimo 10 menciones en los últimos 7 días.
                  </p>
                )}
              </div>
            )}
          </div>

          {/* Widget resumen IA */}
          <div className="card">
            <div className="flex items-center gap-2 mb-3">
              <Sparkles className="w-4 h-4 text-purple-500" />
              <h2 className="text-sm font-semibold text-gray-700">Resumen del día — IA</h2>
              {isAnalyst && (
                <button
                  onClick={() => triggerSummary.mutate()}
                  disabled={triggerSummary.isPending}
                  className="ml-auto text-xs text-purple-600 hover:text-purple-800 flex items-center gap-1"
                >
                  <RefreshCw className={`w-3 h-3 ${triggerSummary.isPending ? 'animate-spin' : ''}`} />
                  {triggerSummary.isPending ? 'Generando...' : 'Generar ahora'}
                </button>
              )}
            </div>

            {summaryLoading ? (
              <p className="text-sm text-gray-400">Cargando...</p>
            ) : summaryData?.items?.length > 0 ? (
              <div>
                <div className="text-xs text-gray-400 mb-2">
                  {format(new Date(summaryData.items[0].summary_date), "EEEE d 'de' MMMM", { locale: es })}
                  &nbsp;·&nbsp;{summaryData.items[0].mention_count} menciones analizadas
                  &nbsp;·&nbsp;
                  <span className="italic">{summaryData.items[0].model_used}</span>
                </div>
                <div className="text-sm text-gray-700 whitespace-pre-line leading-relaxed bg-purple-50 rounded-lg p-3">
                  {summaryData.items[0].summary_text}
                </div>
              </div>
            ) : (
              <div className="text-sm text-gray-400 text-center py-4">
                <p>El resumen se genera automáticamente a las 23:50.</p>
                {isAnalyst && (
                  <p className="mt-1 text-xs">
                    Puedes generarlo manualmente con el botón de arriba
                    (requiere <code className="bg-gray-100 px-1 rounded">GROQ_API_KEY</code>).
                  </p>
                )}
              </div>
            )}
          </div>

          {/* Banner de sugerencias de keywords */}
          {isAnalyst && kwSuggestions?.suggestions?.length > 0 && (
            <div className="card border-amber-200 border bg-amber-50">
              <div className="flex items-start gap-3">
                <Sparkles className="w-4 h-4 text-amber-500 shrink-0 mt-0.5" />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-semibold text-amber-800 mb-1">
                    Sugerimos agregar estas keywords
                  </p>
                  <p className="text-xs text-amber-600 mb-3">
                    Términos frecuentes en las menciones de los últimos 30 días que no están en tu lista.
                  </p>
                  <div className="flex flex-wrap gap-2">
                    {kwSuggestions.suggestions.map(s => (
                      <button
                        key={s.keyword}
                        onClick={() => isAnalyst && quickAddKw.mutate(s.keyword)}
                        disabled={quickAddKw.isPending}
                        className="flex items-center gap-1.5 text-xs bg-white border border-amber-300 text-amber-800 rounded-full px-3 py-1 hover:bg-amber-100 transition-colors font-medium"
                        title={`Relevancia: ${Math.round(s.relevance * 100)}%`}
                      >
                        <Plus className="w-3 h-3" />
                        {s.keyword}
                        <span className="opacity-60">{Math.round(s.relevance * 100)}%</span>
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Panel de entidades relacionadas (NER) */}
          {relatedData?.items?.filter(i => i.entity_type !== '__done__').length > 0 && (
            <div className="card">
              <div className="flex items-center gap-2 mb-3">
                <AtSign className="w-4 h-4 text-teal-500" />
                <h2 className="text-sm font-semibold text-gray-700">
                  Co-menciones frecuentes — últimos 30 días
                </h2>
                <span className="ml-auto text-xs text-gray-400 italic">NER · spaCy</span>
              </div>
              <div className="space-y-3">
                {['PER', 'ORG', 'LOC'].map(type => {
                  const typeItems = relatedData.items.filter(i => i.entity_type === type)
                  if (!typeItems.length) return null
                  const TYPE_CONFIG = {
                    PER: { label: 'Personas',        cls: 'bg-purple-100 text-purple-800' },
                    ORG: { label: 'Organizaciones',  cls: 'bg-blue-100 text-blue-800' },
                    LOC: { label: 'Lugares',         cls: 'bg-teal-100 text-teal-800' },
                  }
                  const { label, cls } = TYPE_CONFIG[type]
                  return (
                    <div key={type}>
                      <p className="text-xs font-medium text-gray-400 mb-1.5">{label}</p>
                      <div className="flex flex-wrap gap-1.5">
                        {typeItems.slice(0, 8).map(item => (
                          <span
                            key={`${item.entity_type}-${item.entity_text}`}
                            className={`text-xs rounded-full px-2.5 py-0.5 font-medium ${cls}`}
                            title={`${item.count} menciones`}
                          >
                            {item.entity_text}
                            <span className="ml-1 opacity-60">({item.count})</span>
                          </span>
                        ))}
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>
          )}

          {/* Panel de anomalías */}
          {anomaliesData?.items?.length > 0 && (
            <div className="card border-orange-200 border">
              <div className="flex items-center gap-2 mb-3">
                <TrendingUp className="w-4 h-4 text-orange-500" />
                <h2 className="text-sm font-semibold text-gray-700">
                  Anomalías detectadas — últimos 7 días
                </h2>
                <span className="ml-auto badge bg-orange-100 text-orange-700">
                  {anomaliesData.total}
                </span>
              </div>
              <div className="space-y-2">
                {anomaliesData.items.slice(0, 5).map(a => {
                  const severityColor =
                    a.severity === 'critical' ? 'text-red-600' :
                    a.severity === 'high'     ? 'text-orange-600' : 'text-yellow-600'
                  const metricLabel =
                    a.metric === 'volume' ? 'Volumen de menciones' : 'Menciones negativas'
                  const unit = a.metric === 'negative_pct' ? '%' : ''
                  // barra proporcional al z-score (max visual = 5)
                  const barWidth = Math.min((a.z_score / 5) * 100, 100)

                  return (
                    <div key={a.id} className="rounded-lg bg-gray-50 px-3 py-2">
                      <div className="flex items-center justify-between text-xs mb-1">
                        <span className="font-medium text-gray-700">{metricLabel}</span>
                        <span className={`font-bold ${severityColor}`}>
                          z = {a.z_score.toFixed(2)}
                        </span>
                      </div>
                      <div className="w-full bg-gray-200 rounded-full h-1.5 mb-1">
                        <div
                          className={`h-1.5 rounded-full ${
                            a.severity === 'critical' ? 'bg-red-500' :
                            a.severity === 'high'     ? 'bg-orange-500' : 'bg-yellow-400'
                          }`}
                          style={{ width: `${barWidth}%` }}
                        />
                      </div>
                      <div className="flex items-center justify-between text-xs text-gray-400">
                        <span>
                          Actual: <strong className="text-gray-600">{a.value.toFixed(1)}{unit}</strong>
                          &nbsp;·&nbsp;
                          Media 7d: {a.baseline.toFixed(1)}{unit}
                        </span>
                        <span>{format(new Date(a.detected_at), "d MMM, HH:mm", { locale: es })}</span>
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>
          )}

          {/* Panel de pronóstico */}
          <div className="card">
            <div className="flex items-center gap-2 mb-3">
              <TrendingUp className="w-4 h-4 text-amber-500" />
              <h2 className="text-sm font-semibold text-gray-700">Pronóstico — próximos 7 días</h2>
              {forecastData?.model_used && (
                <span className="ml-auto text-xs text-gray-400 italic">{forecastData.model_used}</span>
              )}
            </div>
            {hasForecast ? (
              <div>
                <p className="text-xs text-gray-400 mb-2">
                  Línea sólida: historial · Punteada: proyección · Banda: intervalo de confianza 95%
                </p>
                <ReactECharts option={forecastOption} style={{ height: 220 }} />
              </div>
            ) : (
              <div className="text-sm text-gray-400 text-center py-6">
                <p>El pronóstico se genera diariamente a las 00:30.</p>
                <p className="text-xs mt-1">Necesita al menos 7 días con menciones registradas.</p>
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
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="label">Keyword *</label>
                  <input className="input" placeholder="Ej: mira"
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
              </div>

              {/* Operador lógico + segundo término */}
              <div className="mt-3 p-3 bg-gray-50 rounded-lg border border-gray-200">
                <label className="label mb-2">Segundo término <span className="text-gray-400 font-normal">(opcional)</span></label>
                <div className="flex gap-2 items-start flex-wrap">
                  {/* Selector de operador */}
                  <div className="flex rounded-lg border border-gray-300 overflow-hidden shrink-0">
                    {['AND', 'OR', 'NOT'].map(op => (
                      <button
                        key={op}
                        type="button"
                        onClick={() => setKwForm(f => ({ ...f, logic_op: op }))}
                        className={`px-3 py-2 text-xs font-bold transition-colors ${
                          kwForm.logic_op === op
                            ? op === 'AND' ? 'bg-blue-600 text-white'
                            : op === 'OR'  ? 'bg-green-600 text-white'
                            :                'bg-red-600 text-white'
                            : 'bg-white text-gray-500 hover:bg-gray-100'
                        }`}
                      >
                        {op}
                      </button>
                    ))}
                  </div>
                  {/* Campo segundo término */}
                  <input
                    className="input flex-1 min-w-0"
                    placeholder={
                      kwForm.logic_op === 'AND' ? 'Ej: Colombia (debe contener ambos)' :
                      kwForm.logic_op === 'OR'  ? 'Ej: partido (contiene uno u otro)' :
                                                  'Ej: fútbol (excluir si contiene esto)'
                    }
                    value={kwForm.keyword_secondary}
                    onChange={e => setKwForm(f => ({ ...f, keyword_secondary: e.target.value }))}
                  />
                </div>
                {/* Vista previa */}
                {kwForm.keyword && (
                  <p className="text-xs mt-2 flex items-center gap-1 font-mono">
                    <Tag className="w-3 h-3 shrink-0" />
                    {kwForm.keyword_secondary ? (
                      kwForm.logic_op === 'AND' ? <><span className="text-gray-600">"{kwForm.keyword}"</span> <span className="bg-blue-100 text-blue-700 px-1 rounded">Y</span> <span className="text-gray-600">"{kwForm.keyword_secondary}"</span></> :
                      kwForm.logic_op === 'OR'  ? <><span className="text-gray-600">"{kwForm.keyword}"</span> <span className="bg-green-100 text-green-700 px-1 rounded">O</span> <span className="text-gray-600">"{kwForm.keyword_secondary}"</span></> :
                                                  <><span className="text-gray-600">"{kwForm.keyword}"</span> <span className="bg-red-100 text-red-700 px-1 rounded">SIN</span> <span className="text-gray-600">"{kwForm.keyword_secondary}"</span></>
                    ) : (
                      <span className="text-gray-500">"{kwForm.keyword}" — busca menciones con este término</span>
                    )}
                  </p>
                )}
              </div>

              {/* Peso */}
              <div className="mt-3">
                <label className="label">Peso</label>
                <select className="input" value={kwForm.weight}
                  onChange={e => setKwForm(f => ({ ...f, weight: parseInt(e.target.value) }))}>
                  <option value={1}>1 — Normal</option>
                  <option value={2}>2 — Importante</option>
                  <option value={3}>3 — Crítico</option>
                </select>
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
                    <div className="flex-1 min-w-0 flex items-center flex-wrap gap-1">
                      <span className="text-sm font-medium text-gray-800">{kw.keyword}</span>
                      {kw.keyword_secondary && (
                        <>
                          <span className={`text-xs font-bold px-1 rounded ${
                            kw.logic_op === 'OR'  ? 'bg-green-100 text-green-700' :
                            kw.logic_op === 'NOT' ? 'bg-red-100 text-red-700' :
                                                    'bg-blue-100 text-blue-700'
                          }`}>
                            {kw.logic_op === 'OR' ? 'O' : kw.logic_op === 'NOT' ? 'SIN' : 'Y'}
                          </span>
                          <span className="text-xs text-gray-600">"{kw.keyword_secondary}"</span>
                        </>
                      )}
                    </div>
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

      {/* ── Influencers ── */}
      {tab === 'influencers' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between flex-wrap gap-2">
            <div>
              <h3 className="font-semibold text-gray-800">Top Influencers</h3>
              <p className="text-xs text-gray-400">Cuentas con mayor alcance que mencionaron esta entidad</p>
            </div>
            <select className="input w-auto text-sm" value={influDays} onChange={e => setInfluDays(Number(e.target.value))}>
              <option value={7}>Últimos 7 días</option>
              <option value={14}>Últimos 14 días</option>
              <option value={30}>Últimos 30 días</option>
            </select>
          </div>

          {influLoading ? (
            <div className="text-center text-gray-400 py-8">Cargando influencers...</div>
          ) : influencersData?.items?.length > 0 ? (
            <div className="card overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-xs text-gray-500 border-b">
                    <th className="text-left pb-2 font-medium">#</th>
                    <th className="text-left pb-2 font-medium">Usuario</th>
                    <th className="text-right pb-2 font-medium">Seguidores</th>
                    <th className="text-right pb-2 font-medium">Menciones</th>
                    <th className="text-center pb-2 font-medium">Sentimiento</th>
                    <th className="text-center pb-2 font-medium">Bot</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {influencersData.items.map((inf, i) => {
                    const sentColor = inf.avg_sentiment == null ? 'text-gray-400'
                      : inf.avg_sentiment < -0.2 ? 'text-red-600'
                      : inf.avg_sentiment > 0.2 ? 'text-green-600'
                      : 'text-gray-500'
                    const botCls = inf.bot_label === 'bot' ? 'bg-red-100 text-red-700'
                      : inf.bot_label === 'suspicious' ? 'bg-yellow-100 text-yellow-700'
                      : inf.bot_label === 'real' ? 'bg-green-100 text-green-700'
                      : 'bg-gray-100 text-gray-500'
                    return (
                      <tr key={inf.username} className="hover:bg-gray-50">
                        <td className="py-2 text-gray-400">{i + 1}</td>
                        <td className="py-2">
                          <a href={inf.profile_url} target="_blank" rel="noopener noreferrer"
                            className="text-primary-600 hover:underline font-medium">
                            @{inf.username}
                          </a>
                        </td>
                        <td className="py-2 text-right text-gray-700">{inf.followers_count?.toLocaleString() ?? '—'}</td>
                        <td className="py-2 text-right text-gray-700">{inf.mention_count}</td>
                        <td className={`py-2 text-center font-medium ${sentColor}`}>
                          {inf.avg_sentiment != null ? (inf.avg_sentiment > 0 ? '+' : '') + inf.avg_sentiment.toFixed(2) : '—'}
                        </td>
                        <td className="py-2 text-center">
                          {inf.bot_label ? (
                            <span className={`badge ${botCls} text-xs`}>
                              {inf.bot_label === 'bot' ? 'Bot' : inf.bot_label === 'suspicious' ? 'Sospechoso' : inf.bot_label === 'real' ? 'Real' : 'Anónimo'}
                              {inf.bot_score != null ? ` ${Math.round(inf.bot_score * 100)}%` : ''}
                            </span>
                          ) : '—'}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="text-center text-gray-400 py-10 text-sm">
              Sin influencers con datos de seguidores en este período
            </div>
          )}
        </div>
      )}

      {/* ── Reconocimiento Visual — fotos de referencia ── */}
      {tab === 'faces' && (
        <div className="space-y-4">
          <div className="card border-green-200 border bg-green-50 text-sm text-green-800 p-4">
            <p className="font-semibold flex items-center gap-2 mb-1">
              <Camera className="w-4 h-4" /> ¿Cómo funciona?
            </p>
            <p>Agrega fotos de las personas a monitorizar. SONAR analizará las imágenes de las
            menciones de Twitter/X, YouTube y noticias para detectar visualmente su presencia.</p>
            <p className="mt-1 text-xs text-green-700">
              Requiere <code className="bg-green-100 px-1 rounded">FACE_RECOGNITION_ENABLED=true</code> en .env
              y reconstruir el backend (<code className="bg-green-100 px-1 rounded">docker compose build backend</code>).
            </p>
          </div>

          {isAnalyst && (
            <div className="card border-gray-200 border">
              <h3 className="font-semibold text-sm mb-3 flex items-center gap-2">
                <Plus className="w-4 h-4" /> Agregar foto de referencia
              </h3>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="label">Nombre de la persona *</label>
                  <input className="input" placeholder="Ej: Ana Paola Agudelo"
                    value={faceForm.person_name}
                    onChange={e => setFaceForm(f => ({ ...f, person_name: e.target.value }))} />
                </div>
                <div>
                  <label className="label">URL de la foto *</label>
                  <input className="input" placeholder="https://ejemplo.com/foto.jpg"
                    value={faceForm.photo_url}
                    onChange={e => setFaceForm(f => ({ ...f, photo_url: e.target.value }))} />
                </div>
              </div>
              <div className="flex items-center gap-2 mt-3">
                <button
                  onClick={() => addFaceRef.mutate()}
                  disabled={addFaceRef.isPending || !faceForm.person_name || !faceForm.photo_url}
                  className="btn-primary text-sm">
                  {addFaceRef.isPending ? 'Verificando rostro...' : 'Agregar foto'}
                </button>
                <span className="text-xs text-gray-400">
                  Agrega 3–5 fotos por persona con distintos ángulos para mayor precisión
                </span>
              </div>
            </div>
          )}

          {/* Lista de referencias configuradas */}
          <div className="space-y-2">
            {!faceRefsData?.references?.length ? (
              <div className="text-center text-gray-400 py-10 text-sm">
                No hay fotos de referencia configuradas para esta entidad
              </div>
            ) : (
              faceRefsData.references.map(ref => (
                <div key={ref.person_name} className="card flex items-center justify-between py-3">
                  <div className="flex items-center gap-3">
                    <div className="w-9 h-9 rounded-full bg-green-100 flex items-center justify-center">
                      <Camera className="w-4 h-4 text-green-600" />
                    </div>
                    <div>
                      <p className="font-medium text-sm text-gray-800">{ref.person_name}</p>
                      <p className="text-xs text-gray-400">{ref.photo_count} foto(s) de referencia</p>
                    </div>
                  </div>
                  {isAnalyst && (
                    <button onClick={() => delFaceRef.mutate(ref.person_name)}
                      className="text-gray-300 hover:text-red-500 transition-colors">
                      <Trash2 className="w-4 h-4" />
                    </button>
                  )}
                </div>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  )
}
