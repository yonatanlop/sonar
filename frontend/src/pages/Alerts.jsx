import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Bell, Check, ChevronDown, ChevronUp, Sparkles, X, MessageSquare } from 'lucide-react'
import { format } from 'date-fns'
import { es } from 'date-fns/locale'
import toast from 'react-hot-toast'
import client from '../api/client'

const SEVERITY_ICON = { low: 'ℹ️', medium: '⚠️', high: '🔴', critical: '🚨' }

const ACTION_OPTIONS = [
  { value: 'reported_platform',  label: '📣 Reportado a plataforma' },
  { value: 'escalated_mira',     label: '⚖️ Escalado a jurídico MIRA' },
  { value: 'escalated_church',   label: '⛪ Escalado a jurídico iglesia' },
  { value: 'opportunity',        label: '💡 Oportunidad del partido' },
  { value: 'dismissed',          label: '🗑️ Descartado' },
]

const ACTION_BADGE = {
  reported_platform: 'bg-blue-100 text-blue-700',
  escalated_mira:    'bg-purple-100 text-purple-700',
  escalated_church:  'bg-indigo-100 text-indigo-700',
  opportunity:       'bg-green-100 text-green-700',
  dismissed:         'bg-gray-100 text-gray-500',
}

const fetchAlerts = (p) => {
  const params = Object.fromEntries(Object.entries(p).filter(([, v]) => v !== '' && v !== null && v !== undefined))
  return client.get('/alerts', { params }).then(r => r.data)
}

export default function Alerts() {
  const qc = useQueryClient()
  const [filters, setFilters] = useState({
    severity: '', entity_id: '', acknowledged: '', page: 1,
  })
  const [expandedCtx, setExpandedCtx]     = useState(null)
  const [expandedMention, setExpandedMention] = useState(null)
  const [expandedForm, setExpandedForm]   = useState(null)
  const [actionForm, setActionForm]       = useState({ action: '', notes: '' })

  const { data, isLoading } = useQuery({
    queryKey: ['alerts', filters],
    queryFn: () => fetchAlerts(filters),
  })

  const acknowledge = useMutation({
    mutationFn: ({ id, action, notes }) =>
      client.post(`/alerts/${id}/acknowledge`, { action, notes }),
    onSuccess: () => {
      toast.success('Alerta atendida')
      qc.invalidateQueries({ queryKey: ['alerts'] })
      setExpandedForm(null)
      setActionForm({ action: '', notes: '' })
    },
    onError: (err) => toast.error(err?.response?.data?.detail ?? 'Error al atender alerta'),
  })

  const setFilter = (key, val) => setFilters(f => ({ ...f, [key]: val, page: 1 }))

  const openForm = (alertId) => {
    setExpandedForm(alertId)
    setActionForm({ action: '', notes: '' })
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Alertas</h1>
          <p className="text-gray-500 text-sm mt-0.5">Historial de alertas generadas por el sistema</p>
        </div>
      </div>

      {/* Filtros */}
      <div className="card py-4">
        <div className="flex flex-wrap gap-3">
          <select className="input w-auto"
            value={filters.severity}
            onChange={e => setFilter('severity', e.target.value)}>
            <option value="">Todas las severidades</option>
            <option value="critical">🚨 Crítica</option>
            <option value="high">🔴 Alta</option>
            <option value="medium">⚠️ Media</option>
            <option value="low">ℹ️ Baja</option>
          </select>

          <select className="input w-auto"
            value={filters.acknowledged}
            onChange={e => setFilter('acknowledged', e.target.value)}>
            <option value="">Todas</option>
            <option value="false">Sin atender</option>
            <option value="true">Atendidas</option>
          </select>
        </div>
      </div>

      {/* Lista */}
      {isLoading ? (
        <div className="text-center text-gray-400 py-12">Cargando alertas...</div>
      ) : (
        <div className="space-y-2">
          {data?.items?.length === 0 && (
            <div className="card text-center text-gray-400 py-12">
              <Bell className="w-8 h-8 mx-auto mb-2 opacity-30" />
              No hay alertas con los filtros seleccionados
            </div>
          )}

          {data?.items?.map((alert) => (
            <div key={alert.id}
              className={`card py-4 flex items-start gap-4 ${!alert.acknowledged ? 'border-l-4 border-l-red-400' : ''}`}>
              <span className="text-2xl shrink-0">{SEVERITY_ICON[alert.severity]}</span>

              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className={`badge badge-${alert.severity}`}>
                    {alert.severity.toUpperCase()}
                  </span>
                  <span className="font-semibold text-gray-800 text-sm">{alert.entity_name}</span>
                  <span className="text-gray-400 text-xs">·</span>
                  <span className="text-gray-500 text-xs">{alert.rule_type?.replace(/_/g, ' ')}</span>
                  {!alert.acknowledged && (
                    <span className="badge bg-blue-100 text-blue-700">● Sin atender</span>
                  )}
                  {alert.acknowledged && alert.action_taken && (
                    <span className={`badge ${ACTION_BADGE[alert.action_taken] ?? 'bg-gray-100 text-gray-500'}`}>
                      {ACTION_OPTIONS.find(o => o.value === alert.action_taken)?.label ?? alert.action_taken}
                    </span>
                  )}
                </div>
                <p className="text-sm text-gray-700 mt-1">{alert.message}</p>
                <p className="text-xs text-gray-400 mt-1">
                  {format(new Date(alert.triggered_at), "d 'de' MMM yyyy, HH:mm", { locale: es })}
                  {alert.acknowledged && alert.acknowledged_by_name && (
                    <> · Atendida por <strong>{alert.acknowledged_by_name}</strong></>
                  )}
                </p>
                {alert.acknowledged && alert.action_notes && (
                  <p className="text-xs text-gray-500 mt-1 italic">"{alert.action_notes}"</p>
                )}

                {/* Formulario inline para atender */}
                {expandedForm === alert.id && (
                  <div className="mt-3 p-3 bg-gray-50 rounded-lg border border-gray-200 space-y-3">
                    <div>
                      <label className="label text-xs">Acción tomada *</label>
                      <select className="input text-sm" value={actionForm.action}
                        onChange={e => setActionForm(f => ({ ...f, action: e.target.value }))}>
                        <option value="">Seleccionar acción...</option>
                        {ACTION_OPTIONS.map(o => (
                          <option key={o.value} value={o.value}>{o.label}</option>
                        ))}
                      </select>
                    </div>
                    <div>
                      <label className="label text-xs">Notas <span className="font-normal text-gray-400">(opcional)</span></label>
                      <textarea
                        className="input text-sm resize-none"
                        rows={2}
                        maxLength={200}
                        placeholder="Descripción breve de la acción tomada..."
                        value={actionForm.notes}
                        onChange={e => setActionForm(f => ({ ...f, notes: e.target.value }))}
                      />
                      <p className="text-xs text-gray-400 text-right">{actionForm.notes.length}/200</p>
                    </div>
                    <div className="flex gap-2">
                      <button
                        onClick={() => acknowledge.mutate({ id: alert.id, ...actionForm })}
                        disabled={acknowledge.isPending || !actionForm.action}
                        className="btn-primary text-xs py-1.5">
                        {acknowledge.isPending ? 'Guardando...' : <><Check className="w-3.5 h-3.5" /> Confirmar</>}
                      </button>
                      <button onClick={() => setExpandedForm(null)} className="btn-secondary text-xs py-1.5">
                        <X className="w-3.5 h-3.5" /> Cancelar
                      </button>
                    </div>
                  </div>
                )}

                {/* Mención que originó la alerta */}
                {alert.mention && (
                  <div className="mt-2">
                    <button
                      onClick={() => setExpandedMention(expandedMention === alert.id ? null : alert.id)}
                      className="flex items-center gap-1 text-xs text-blue-600 hover:text-blue-800 font-medium"
                    >
                      <MessageSquare className="w-3 h-3" />
                      Ver mención
                      {expandedMention === alert.id
                        ? <ChevronUp className="w-3 h-3" />
                        : <ChevronDown className="w-3 h-3" />}
                    </button>
                    {expandedMention === alert.id && (
                      <div className="mt-2 p-3 bg-blue-50 rounded-lg border border-blue-100 text-xs text-gray-700 space-y-1.5">
                        <div className="flex items-center gap-2 flex-wrap">
                          {alert.mention.author_username && (
                            <span className="font-medium text-gray-800">@{alert.mention.author_username}</span>
                          )}
                          {alert.mention.platform_name && (
                            <span className="text-gray-500">· {alert.mention.platform_name}</span>
                          )}
                          {alert.mention.sentiment_label && (
                            <span className={{
                              very_negative: 'text-red-600 font-semibold',
                              negative:      'text-orange-500 font-semibold',
                              neutral:       'text-gray-500',
                              positive:      'text-green-600 font-semibold',
                            }[alert.mention.sentiment_label] ?? 'text-gray-500'}>
                              {alert.mention.sentiment_label.replace('_', ' ')}
                            </span>
                          )}
                          {alert.mention.urgency_score != null && (
                            <span className="text-gray-500">· urgencia {Math.round(alert.mention.urgency_score)}/100</span>
                          )}
                        </div>
                        <p className="leading-relaxed line-clamp-4">{alert.mention.content}</p>
                        {alert.mention.url && (
                          <a href={alert.mention.url} target="_blank" rel="noreferrer"
                            className="text-blue-500 hover:underline inline-block">
                            Ver publicación ↗
                          </a>
                        )}
                      </div>
                    )}
                  </div>
                )}

                {/* Contexto IA — solo en alertas de anomalía */}
                {alert.rule_type === 'anomaly_detected' && (
                  <div className="mt-2">
                    {alert.context_explanation ? (
                      <>
                        <button
                          onClick={() => setExpandedCtx(expandedCtx === alert.id ? null : alert.id)}
                          className="flex items-center gap-1 text-xs text-purple-600 hover:text-purple-800 font-medium"
                        >
                          <Sparkles className="w-3 h-3" />
                          ¿Por qué ocurrió esto?
                          {expandedCtx === alert.id
                            ? <ChevronUp className="w-3 h-3" />
                            : <ChevronDown className="w-3 h-3" />}
                        </button>
                        {expandedCtx === alert.id && (
                          <div className="mt-2 p-3 bg-purple-50 rounded-lg border border-purple-100 text-xs text-gray-700 leading-relaxed">
                            <div className="flex items-center gap-1 mb-1.5 text-purple-500 font-medium">
                              <Sparkles className="w-3 h-3" />
                              Análisis de contexto — IA
                            </div>
                            {alert.context_explanation}
                          </div>
                        )}
                      </>
                    ) : (
                      <span className="text-xs text-gray-400 italic">
                        Contexto IA pendiente (requiere GROQ_API_KEY)
                      </span>
                    )}
                  </div>
                )}
              </div>

              <div className="flex gap-2 shrink-0">
                {!alert.acknowledged && expandedForm !== alert.id && (
                  <button
                    onClick={() => openForm(alert.id)}
                    className="btn-secondary text-xs py-1.5"
                  >
                    <Check className="w-3.5 h-3.5" /> Atender
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Paginación */}
      {data?.total > 20 && (
        <div className="flex justify-center gap-2">
          <button
            disabled={filters.page === 1}
            onClick={() => setFilters(f => ({ ...f, page: f.page - 1 }))}
            className="btn-secondary text-sm"
          >
            ← Anterior
          </button>
          <span className="text-sm text-gray-500 self-center">
            Página {filters.page} de {Math.ceil(data.total / 20)}
          </span>
          <button
            disabled={filters.page >= Math.ceil(data.total / 20)}
            onClick={() => setFilters(f => ({ ...f, page: f.page + 1 }))}
            className="btn-secondary text-sm"
          >
            Siguiente →
          </button>
        </div>
      )}
    </div>
  )
}
