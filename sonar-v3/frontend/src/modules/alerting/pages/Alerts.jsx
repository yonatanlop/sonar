import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { format } from 'date-fns'
import { es } from 'date-fns/locale'
import { ChevronDown, ChevronUp } from 'lucide-react'
import toast from 'react-hot-toast'
import client from '../../../shared/api/client'

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
  const params = Object.fromEntries(Object.entries(p).filter(([, v]) => v !== '' && v != null))
  return client.get('/alerts', { params }).then(r => r.data)
}

export default function Alerts() {
  const qc = useQueryClient()
  const [filters, setFilters] = useState({ severity: '', acknowledged: '', page: 1 })
  const [expandedCtx, setExpandedCtx]   = useState(null)
  const [expandedForm, setExpandedForm] = useState(null)
  const [actionForm, setActionForm]     = useState({ action: '', notes: '' })

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
    onError: (e) => toast.error(e?.response?.data?.detail ?? 'Error al atender alerta'),
  })

  const setFilter = (k, v) => setFilters(f => ({ ...f, [k]: v, page: 1 }))
  const alerts = data?.items ?? data ?? []

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Alertas</h1>
        <p className="text-gray-500 text-sm mt-0.5">Historial de alertas generadas por el sistema</p>
      </div>

      <div className="card py-4">
        <div className="flex flex-wrap gap-3">
          <select className="input w-auto" value={filters.severity} onChange={e => setFilter('severity', e.target.value)}>
            <option value="">Todas las severidades</option>
            <option value="critical">🚨 Crítica</option>
            <option value="high">🔴 Alta</option>
            <option value="medium">⚠️ Media</option>
            <option value="low">ℹ️ Baja</option>
          </select>
          <select className="input w-auto" value={filters.acknowledged} onChange={e => setFilter('acknowledged', e.target.value)}>
            <option value="">Todas</option>
            <option value="false">Sin atender</option>
            <option value="true">Atendidas</option>
          </select>
        </div>
      </div>

      {isLoading ? (
        <div className="text-center text-gray-400 py-12">Cargando alertas...</div>
      ) : (
        <div className="space-y-3">
          {alerts.map(alert => (
            <div key={alert.id} className="card p-4">
              <div className="flex items-start gap-3">
                <span className="text-xl mt-0.5">{SEVERITY_ICON[alert.severity]}</span>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className={`badge badge-${alert.severity}`}>{alert.severity.toUpperCase()}</span>
                    <span className="font-medium text-gray-900 text-sm">{alert.entity_name}</span>
                    {alert.action_taken && (
                      <span className={`badge ${ACTION_BADGE[alert.action_taken]}`}>
                        {ACTION_OPTIONS.find(a => a.value === alert.action_taken)?.label ?? alert.action_taken}
                      </span>
                    )}
                    <span className="text-xs text-gray-400 ml-auto">
                      {format(new Date(alert.triggered_at), "d MMM yyyy HH:mm", { locale: es })}
                    </span>
                  </div>
                  <p className="text-sm text-gray-700 mt-1">{alert.message}</p>

                  {alert.context && (
                    <div className="mt-2">
                      <button
                        onClick={() => setExpandedCtx(expandedCtx === alert.id ? null : alert.id)}
                        className="text-xs text-primary-600 hover:underline flex items-center gap-1"
                      >
                        {expandedCtx === alert.id ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
                        Contexto
                      </button>
                      {expandedCtx === alert.id && (
                        <div className="mt-2 p-3 bg-gray-50 rounded-lg text-xs text-gray-600 space-y-1">
                          {Object.entries(alert.context).map(([k, v]) => (
                            <div key={k}><span className="font-medium">{k}:</span> {String(v)}</div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}

                  {!alert.acknowledged && (
                    <div className="mt-3">
                      {expandedForm === alert.id ? (
                        <div className="space-y-2">
                          <select
                            className="input w-auto text-sm"
                            value={actionForm.action}
                            onChange={e => setActionForm(f => ({ ...f, action: e.target.value }))}
                          >
                            <option value="">Selecciona una acción</option>
                            {ACTION_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
                          </select>
                          <textarea
                            className="input text-sm"
                            rows={2}
                            placeholder="Notas (opcional)"
                            value={actionForm.notes}
                            onChange={e => setActionForm(f => ({ ...f, notes: e.target.value }))}
                          />
                          <div className="flex gap-2">
                            <button
                              className="btn-primary text-xs py-1.5 px-3"
                              disabled={!actionForm.action || acknowledge.isPending}
                              onClick={() => acknowledge.mutate({ id: alert.id, ...actionForm })}
                            >
                              Confirmar acción
                            </button>
                            <button className="btn-secondary text-xs py-1.5 px-3"
                              onClick={() => setExpandedForm(null)}>
                              Cancelar
                            </button>
                          </div>
                        </div>
                      ) : (
                        <button
                          className="btn-secondary text-xs py-1.5 px-3"
                          onClick={() => setExpandedForm(alert.id)}
                        >
                          Atender alerta
                        </button>
                      )}
                    </div>
                  )}
                </div>
              </div>
            </div>
          ))}
          {alerts.length === 0 && (
            <div className="text-center text-gray-400 py-12">No hay alertas con los filtros seleccionados</div>
          )}
        </div>
      )}
    </div>
  )
}
