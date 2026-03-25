import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Bell, Check, ChevronDown, ChevronUp, Sparkles } from 'lucide-react'
import { format } from 'date-fns'
import { es } from 'date-fns/locale'
import toast from 'react-hot-toast'
import client from '../api/client'

const SEVERITY_ICON = { low: 'ℹ️', medium: '⚠️', high: '🔴', critical: '🚨' }

const fetchAlerts = (p) => {
  const params = Object.fromEntries(Object.entries(p).filter(([, v]) => v !== '' && v !== null && v !== undefined))
  return client.get('/alerts', { params }).then(r => r.data)
}

export default function Alerts() {
  const qc = useQueryClient()
  const [filters, setFilters] = useState({
    severity: '', entity_id: '', acknowledged: '', page: 1,
  })
  const [expandedCtx, setExpandedCtx] = useState(null)  // id de alerta con contexto expandido

  const { data, isLoading } = useQuery({
    queryKey: ['alerts', filters],
    queryFn: () => fetchAlerts(filters),
  })

  const acknowledge = useMutation({
    mutationFn: (id) => client.post(`/alerts/${id}/acknowledge`),
    onSuccess: () => {
      toast.success('Alerta marcada como atendida')
      qc.invalidateQueries({ queryKey: ['alerts'] })
    },
  })

  const setFilter = (key, val) => setFilters(f => ({ ...f, [key]: val, page: 1 }))

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
                  <span className="text-gray-500 text-xs">{alert.rule_type.replace('_', ' ')}</span>
                  {!alert.acknowledged && (
                    <span className="badge bg-blue-100 text-blue-700">● Sin atender</span>
                  )}
                </div>
                <p className="text-sm text-gray-700 mt-1">{alert.message}</p>
                <p className="text-xs text-gray-400 mt-1">
                  {format(new Date(alert.triggered_at), "d 'de' MMM yyyy, HH:mm", { locale: es })}
                  {alert.acknowledged && alert.acknowledged_by_name && (
                    <> · Atendida por <strong>{alert.acknowledged_by_name}</strong></>
                  )}
                </p>

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
                {!alert.acknowledged && (
                  <button
                    onClick={() => acknowledge.mutate(alert.id)}
                    disabled={acknowledge.isPending}
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
