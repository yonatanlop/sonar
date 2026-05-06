import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Inbox, ExternalLink, AlertTriangle, AlertCircle,
  CheckCircle, Clock, ChevronRight, User, Globe,
} from 'lucide-react'
import toast from 'react-hot-toast'
import client from '../api/client'
import { useAlertStore } from '../store/alertStore'

const fetchInbox  = () => client.get('/alerts/inbox').then(r => r.data)

const PLATFORM_LABEL = {
  reddit:    'Reddit',
  youtube:   'YouTube',
  twitter:   'Twitter/X',
  instagram: 'Instagram',
  facebook:  'Facebook',
  rss:       'RSS',
}

const SENTIMENT_BADGE = {
  negative:      { text: 'Negativo',      cls: 'bg-orange-100 text-orange-700 border-orange-200' },
  very_negative: { text: 'Muy negativo',  cls: 'bg-red-100 text-red-700 border-red-200' },
}

const SEVERITY_DOT = {
  high:   'bg-red-500',
  medium: 'bg-orange-400',
}

const ACTIONS = [
  { value: 'reported_platform',      label: 'Reportar en la plataforma' },
  { value: 'reported_international', label: 'Reportar a instancias internacionales' },
  { value: 'reported_fiscalia',      label: 'Reportar a Fiscalía / Policía' },
  { value: 'account_closed',         label: 'Cuenta cerrada como resultado' },
  { value: 'escalated_mira',         label: 'Escalar a equipo MIRA' },
  { value: 'escalated_church',       label: 'Escalar a dirección iglesia' },
  { value: 'opportunity',            label: 'Marcar como oportunidad' },
  { value: 'dismissed',              label: 'Descartar' },
]

function timeAgo(isoStr) {
  const diff = Math.floor((Date.now() - new Date(isoStr)) / 1000)
  if (diff < 60)   return 'hace un momento'
  if (diff < 3600) return `hace ${Math.floor(diff / 60)} min`
  if (diff < 86400) return `hace ${Math.floor(diff / 3600)} h`
  return `hace ${Math.floor(diff / 86400)} d`
}

export default function MentionInbox() {
  const qc = useQueryClient()
  const setInboxCount = useAlertStore((s) => s.setInboxCount)

  const [selected, setSelected]   = useState(null)
  const [action, setAction]       = useState('')
  const [notes, setNotes]         = useState('')

  const { data: items = [], isLoading } = useQuery({
    queryKey: ['inbox'],
    queryFn:  fetchInbox,
    refetchInterval: 30_000,
  })

  const treat = useMutation({
    mutationFn: ({ id, action, notes }) =>
      client.post(`/alerts/${id}/acknowledge`, { action, notes }),
    onSuccess: (_, { id }) => {
      toast.success('Tratamiento guardado')
      qc.invalidateQueries({ queryKey: ['inbox'] })
      qc.invalidateQueries({ queryKey: ['inbox-count'] })
      // Actualizar badge en sidebar
      const remaining = items.filter(i => i.id !== id).length
      setInboxCount(remaining > 0 ? remaining - 1 : 0)
      // Seleccionar el siguiente ítem
      const idx = items.findIndex(i => i.id === id)
      const next = items[idx + 1] ?? items[idx - 1] ?? null
      setSelected(next)
      setAction('')
      setNotes('')
    },
    onError: (err) => {
      toast.error(err?.response?.data?.detail ?? 'Error al guardar')
    },
  })

  const handleSelect = (item) => {
    setSelected(item)
    setAction('')
    setNotes('')
  }

  const mention = selected?.mention

  return (
    <div className="flex h-[calc(100vh-4rem)] gap-0 -m-6 overflow-hidden">

      {/* ── Lista izquierda ─────────────────────────────────── */}
      <div className="w-full md:w-80 lg:w-96 border-r border-gray-200 flex flex-col bg-white shrink-0">
        <div className="px-4 py-4 border-b border-gray-100">
          <div className="flex items-center gap-2">
            <Inbox className="w-5 h-5 text-primary-600" />
            <h1 className="font-semibold text-gray-900">Bandeja de menciones</h1>
          </div>
          <p className="text-xs text-gray-500 mt-0.5">
            {isLoading ? 'Cargando…' : `${items.length} pendiente${items.length !== 1 ? 's' : ''}`}
          </p>
        </div>

        <div className="flex-1 overflow-y-auto divide-y divide-gray-100">
          {isLoading ? (
            <div className="text-center text-gray-400 py-12 text-sm">Cargando bandeja…</div>
          ) : items.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-16 text-gray-400 gap-3">
              <CheckCircle className="w-10 h-10 text-green-400" />
              <p className="text-sm font-medium">Bandeja vacía</p>
              <p className="text-xs text-center px-4">No hay menciones negativas pendientes de tratamiento</p>
            </div>
          ) : (
            items.map(item => {
              const badge   = SENTIMENT_BADGE[item.mention?.sentiment_label]
              const dot     = SEVERITY_DOT[item.severity] ?? 'bg-gray-400'
              const isActive = selected?.id === item.id
              return (
                <button
                  key={item.id}
                  onClick={() => handleSelect(item)}
                  className={`w-full text-left px-4 py-3 hover:bg-gray-50 transition-colors ${
                    isActive ? 'bg-primary-50 border-l-2 border-primary-500' : ''
                  }`}
                >
                  <div className="flex items-start justify-between gap-2 mb-1">
                    <span className="font-medium text-sm text-gray-900 truncate">{item.entity_name}</span>
                    <span className={`w-2 h-2 rounded-full shrink-0 mt-1.5 ${dot}`} />
                  </div>
                  <p className="text-xs text-gray-500 line-clamp-2 mb-1.5">
                    {item.mention?.content ?? item.message}
                  </p>
                  <div className="flex items-center gap-2 text-xs text-gray-400">
                    <Globe className="w-3 h-3" />
                    <span>{PLATFORM_LABEL[item.mention?.platform_code] ?? item.mention?.platform_code ?? '—'}</span>
                    <span>·</span>
                    <Clock className="w-3 h-3" />
                    <span>{timeAgo(item.triggered_at)}</span>
                  </div>
                  {badge && (
                    <span className={`mt-1.5 inline-block text-xs px-2 py-0.5 rounded-full border font-medium ${badge.cls}`}>
                      {badge.text}
                    </span>
                  )}
                </button>
              )
            })
          )}
        </div>
      </div>

      {/* ── Panel de tratamiento ─────────────────────────────── */}
      <div className="flex-1 overflow-y-auto bg-gray-50">
        {!selected ? (
          <div className="flex flex-col items-center justify-center h-full text-gray-400 gap-3">
            <Inbox className="w-12 h-12 text-gray-300" />
            <p className="text-sm font-medium">Selecciona una mención</p>
            <p className="text-xs">Haz clic en un ítem de la lista para tratarlo</p>
          </div>
        ) : (
          <div className="max-w-2xl mx-auto p-6 space-y-5">

            {/* Cabecera */}
            <div>
              <div className="flex items-center gap-2 text-xs text-gray-500 mb-1">
                <span className="font-medium text-gray-700">{selected.entity_name}</span>
                <ChevronRight className="w-3 h-3" />
                <span>{PLATFORM_LABEL[mention?.platform_code] ?? mention?.platform_code}</span>
                <ChevronRight className="w-3 h-3" />
                <span>{timeAgo(selected.triggered_at)}</span>
              </div>
              <div className="flex items-center gap-2">
                {selected.severity === 'high'
                  ? <AlertCircle className="w-5 h-5 text-red-500" />
                  : <AlertTriangle className="w-5 h-5 text-orange-400" />
                }
                <h2 className="text-lg font-semibold text-gray-900">
                  Mención {SENTIMENT_BADGE[mention?.sentiment_label]?.text?.toLowerCase() ?? 'negativa'}
                </h2>
              </div>
            </div>

            {/* Datos de la mención */}
            <div className="card space-y-3">
              <div className="flex items-center gap-3 text-sm text-gray-600">
                <User className="w-4 h-4 shrink-0 text-gray-400" />
                <span>@{mention?.author_username ?? 'anónimo'}</span>
                <span className="text-gray-300">|</span>
                <Globe className="w-4 h-4 shrink-0 text-gray-400" />
                <span>{PLATFORM_LABEL[mention?.platform_code] ?? mention?.platform_code}</span>
                {mention?.url && (
                  <>
                    <span className="text-gray-300">|</span>
                    <a href={mention.url} target="_blank" rel="noopener noreferrer"
                       className="flex items-center gap-1 text-primary-600 hover:underline text-xs">
                      Ver original <ExternalLink className="w-3 h-3" />
                    </a>
                  </>
                )}
              </div>

              <p className="text-gray-800 text-sm leading-relaxed whitespace-pre-wrap border-l-2 border-gray-200 pl-3">
                {mention?.content ?? '— contenido no disponible —'}
              </p>

              <div className="flex flex-wrap gap-3 pt-1 text-xs">
                {mention?.sentiment_label && (
                  <span className={`px-2 py-0.5 rounded-full border font-medium ${
                    SENTIMENT_BADGE[mention.sentiment_label]?.cls ?? ''
                  }`}>
                    {SENTIMENT_BADGE[mention.sentiment_label]?.text}
                    {mention.sentiment_score ? ` (${(mention.sentiment_score * 100).toFixed(0)}%)` : ''}
                  </span>
                )}
                {mention?.urgency_score != null && (
                  <span className={`px-2 py-0.5 rounded-full border font-medium ${
                    mention.urgency_score >= 70
                      ? 'bg-red-50 text-red-700 border-red-200'
                      : mention.urgency_score >= 40
                        ? 'bg-orange-50 text-orange-700 border-orange-200'
                        : 'bg-gray-100 text-gray-600 border-gray-200'
                  }`}>
                    Urgencia {mention.urgency_score}/100
                  </span>
                )}
                {mention?.is_hate_speech && (
                  <span className="px-2 py-0.5 rounded-full border bg-red-100 text-red-700 border-red-200 font-medium">
                    Discurso de odio
                  </span>
                )}
              </div>
            </div>

            {/* Formulario de tratamiento */}
            <div className="card space-y-4">
              <h3 className="font-medium text-gray-900 text-sm">¿Qué acción tomas?</h3>

              <div className="space-y-2">
                {ACTIONS.map(a => (
                  <label key={a.value}
                    className={`flex items-center gap-3 p-2.5 rounded-lg border cursor-pointer transition-colors ${
                      action === a.value
                        ? 'border-primary-400 bg-primary-50'
                        : 'border-gray-200 hover:border-gray-300 hover:bg-gray-50'
                    }`}>
                    <input type="radio" name="action" value={a.value}
                      checked={action === a.value}
                      onChange={() => setAction(a.value)}
                      className="accent-primary-600" />
                    <span className="text-sm text-gray-700">{a.label}</span>
                  </label>
                ))}
              </div>

              <div>
                <label className="label">Notas <span className="text-gray-400 font-normal">(opcional)</span></label>
                <textarea
                  className="input resize-none"
                  rows={3}
                  placeholder="Agrega contexto o instrucciones adicionales..."
                  value={notes}
                  onChange={e => setNotes(e.target.value)}
                />
              </div>

              <div className="flex gap-2 pt-1">
                <button
                  onClick={() => treat.mutate({ id: selected.id, action, notes })}
                  disabled={treat.isPending || !action}
                  className="btn-primary flex-1">
                  {treat.isPending ? 'Guardando…' : 'Guardar tratamiento'}
                </button>
                {mention?.id && (
                  <Link
                    to={`/mentions?highlight=${mention.id}`}
                    className="btn-secondary flex items-center gap-1.5 whitespace-nowrap">
                    Ver mención <ExternalLink className="w-3.5 h-3.5" />
                  </Link>
                )}
              </div>
            </div>

          </div>
        )}
      </div>
    </div>
  )
}
