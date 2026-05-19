import { useState, useMemo } from 'react'
import { Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Inbox, ExternalLink, AlertTriangle, AlertCircle,
  CheckCircle, Clock, ChevronRight, User, Globe, Scale, X, HelpCircle, ChevronDown, Flag,
} from 'lucide-react'
import toast from 'react-hot-toast'
import client from '../api/client'
import { useAlertStore } from '../store/alertStore'
import { useAuthStore } from '../store/authStore'

const fetchInbox = (status, sortBy, topic) =>
  client.get('/alerts/inbox', {
    params: {
      status,
      sort_by: sortBy,
      ...(topic ? { topic } : {}),
    },
  }).then(r => r.data)

function fmtFollowers(n) {
  if (!n) return null
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000)     return `${(n / 1_000).toFixed(0)}K`
  return String(n)
}

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
  const isAnalyst = useAuthStore((s) => s.isAnalyst())
  const isAdmin   = useAuthStore((s) => s.isAdmin())

  const [selected, setSelected]   = useState(null)
  const [action, setAction]       = useState('')
  const [notes, setNotes]         = useState('')

  // Filtros y ordenamiento
  const [statusFilter, setStatusFilter] = useState('pending')
  const [sortBy, setSortBy]             = useState('date')
  const [topicFilter, setTopicFilter]   = useState('')

  // Corrección de sentimiento
  const [feedbackOpen, setFeedbackOpen]   = useState(false)
  const [feedbackLabel, setFeedbackLabel] = useState('')
  const [feedbackNotes, setFeedbackNotes] = useState('')

  // Modal de escalación jurídica
  const [showEscalate, setShowEscalate] = useState(false)
  const [escTarget, setEscTarget]       = useState('')
  const [escNotes, setEscNotes]         = useState('')

  // Protocolo in-app
  const [showProtocol, setShowProtocol] = useState(false)

  const { data: items = [], isLoading } = useQuery({
    queryKey: ['inbox', statusFilter, sortBy, topicFilter],
    queryFn:  () => fetchInbox(statusFilter, sortBy, topicFilter),
    refetchInterval: 30_000,
  })

  const topics = useMemo(() =>
    [...new Set((items || []).map(i => i.mention?.topic_label).filter(Boolean))],
    [items]
  )

  const escalate = useMutation({
    mutationFn: ({ mention_id, target, notes }) =>
      client.post('/legal/escalations', { mention_id, target, notes }),
    onSuccess: () => {
      toast.success('Escalado al equipo jurídico')
      setShowEscalate(false)
      setEscTarget('')
      setEscNotes('')
    },
    onError: (err) => {
      toast.error(err?.response?.data?.detail ?? 'Error al escalar')
    },
  })

  const treat = useMutation({
    mutationFn: ({ id, action, notes }) =>
      client.post(`/alerts/${id}/acknowledge`, { action, notes }),
    onSuccess: (_, { id }) => {
      toast.success('Tratamiento guardado')
      qc.invalidateQueries({ queryKey: ['inbox'] })
      qc.invalidateQueries({ queryKey: ['inbox-count'] })
      qc.invalidateQueries({ queryKey: ['mentions'] })
      // Actualizar badge en sidebar
      setInboxCount(n => Math.max(0, n - 1))
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

  const submitFeedback = useMutation({
    mutationFn: ({ mentionId, label, notes }) =>
      client.post(`/mentions/${mentionId}/feedback`, { corrected_label: label, notes }),
    onSuccess: () => {
      toast.success('Corrección de sentimiento guardada')
      qc.invalidateQueries({ queryKey: ['inbox'] })
      setFeedbackOpen(false)
      setFeedbackNotes('')
    },
    onError: (err) => {
      toast.error(err?.response?.data?.detail ?? 'Error al guardar la corrección')
    },
  })

  const handleSelect = (item) => {
    setSelected(item)
    setAction('')
    setNotes('')
    setFeedbackOpen(false)
    setFeedbackNotes('')
  }

  const mention = selected?.mention

  return (
    <div className="flex h-[calc(100vh-4rem)] gap-0 -m-6 overflow-hidden">

      {/* ── Lista izquierda ─────────────────────────────────── */}
      <div className="w-full md:w-80 lg:w-96 border-r border-gray-200 flex flex-col bg-white shrink-0">
        <div className="px-4 py-4 border-b border-gray-100 space-y-3">
          <div className="flex items-center gap-2">
            <Inbox className="w-5 h-5 text-primary-600" />
            <h1 className="font-semibold text-gray-900">Bandeja de menciones</h1>
          </div>
          <p className="text-xs text-gray-500">
            {isLoading ? 'Cargando…' : `${items.length} elemento${items.length !== 1 ? 's' : ''}`}
          </p>

          {/* Filtro de estado */}
          <div className="flex rounded-lg border border-gray-200 overflow-hidden text-xs w-full">
            {[['pending','🚨 Pendientes'],['all','Todas'],['managed','✓ Gestionadas']].map(([v, label]) => (
              <button key={v}
                className={`flex-1 px-2 py-1.5 font-medium transition-colors ${
                  statusFilter === v ? 'bg-primary-600 text-white' : 'bg-white text-gray-600 hover:bg-gray-50'
                }`}
                onClick={() => setStatusFilter(v)}>{label}</button>
            ))}
          </div>

          {/* Ordenar y tema */}
          <div className="flex gap-2">
            <select className="input text-xs py-1.5 flex-1"
              value={sortBy} onChange={e => setSortBy(e.target.value)}>
              <option value="date">📅 Más recientes</option>
              <option value="urgency">🔥 Mayor urgencia</option>
              <option value="followers">👥 Más seguidores</option>
            </select>
            <select className="input text-xs py-1.5 flex-1"
              value={topicFilter} onChange={e => setTopicFilter(e.target.value)}>
              <option value="">📋 Todos los temas</option>
              {topics.map(t => <option key={t} value={t}>{t}</option>)}
            </select>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto divide-y divide-gray-100">
          {isLoading ? (
            <div className="text-center text-gray-400 py-12 text-sm">Cargando bandeja…</div>
          ) : items.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-16 text-gray-400 gap-3">
              <CheckCircle className="w-10 h-10 text-green-400" />
              <p className="text-sm font-medium">Sin resultados</p>
              <p className="text-xs text-center px-4">
                {statusFilter === 'pending'
                  ? 'No hay menciones negativas pendientes de tratamiento'
                  : statusFilter === 'managed'
                    ? 'No hay menciones gestionadas con los filtros actuales'
                    : 'No se encontraron menciones con los filtros seleccionados'}
              </p>
            </div>
          ) : (
            items.map(item => {
              const badge    = SENTIMENT_BADGE[item.mention?.sentiment_label]
              const dot      = SEVERITY_DOT[item.severity] ?? 'bg-gray-400'
              const isActive = selected?.id === item.id
              const followers = fmtFollowers(item.mention?.author_followers)
              return (
                <button
                  key={item.id}
                  onClick={() => handleSelect(item)}
                  className={`w-full text-left px-4 py-3 hover:bg-gray-50 transition-colors ${
                    isActive ? 'bg-primary-50 border-l-2 border-primary-500' : ''
                  }`}
                >
                  <div className="flex items-start justify-between gap-2 mb-1">
                    <div className="flex items-center gap-1.5 min-w-0">
                      <span className="font-medium text-sm text-gray-900 truncate">{item.entity_name}</span>
                      {item.mention?.is_verified && (
                        <span title="Cuenta verificada" className="shrink-0 text-blue-500 text-xs">✅</span>
                      )}
                      <span title={item.mention?.acknowledged ? 'Gestionada' : 'Pendiente'}
                        className="shrink-0 text-xs">
                        {item.mention?.acknowledged ? '✓' : '🚨'}
                      </span>
                    </div>
                    <span className={`w-2 h-2 rounded-full shrink-0 mt-1.5 ${dot}`} />
                  </div>
                  <p className="text-xs text-gray-500 line-clamp-2 mb-1.5">
                    {item.mention?.content ?? item.message}
                  </p>
                  <div className="flex items-center gap-2 text-xs text-gray-400 flex-wrap">
                    <Globe className="w-3 h-3" />
                    <span>{PLATFORM_LABEL[item.mention?.platform_code] ?? item.mention?.platform_code ?? '—'}</span>
                    <span>·</span>
                    <Clock className="w-3 h-3" />
                    <span>{timeAgo(item.triggered_at)}</span>
                    {followers && (
                      <>
                        <span>·</span>
                        <span className="flex items-center gap-0.5">👥 {followers}</span>
                      </>
                    )}
                  </div>
                  <div className="flex flex-wrap gap-1 mt-1.5">
                    {badge && (
                      <span className={`inline-block text-xs px-2 py-0.5 rounded-full border font-medium ${badge.cls}`}>
                        {badge.text}
                      </span>
                    )}
                    {item.mention?.topic_label && (
                      <span className="text-[10px] bg-purple-100 text-purple-700 px-1.5 py-0.5 rounded-full border border-purple-200">
                        {item.mention.topic_label}
                      </span>
                    )}
                  </div>
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
              <div className="flex items-center gap-3 text-sm text-gray-600 flex-wrap">
                <User className="w-4 h-4 shrink-0 text-gray-400" />
                <span className="flex items-center gap-1">
                  @{mention?.author_username ?? 'anónimo'}
                  {mention?.is_verified && <span title="Cuenta verificada" className="text-blue-500">✅</span>}
                </span>
                {mention?.author_followers > 0 && (
                  <span className="text-xs text-gray-500 flex items-center gap-0.5">
                    👥 {fmtFollowers(mention.author_followers)} seguidores
                  </span>
                )}
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
                {mention?.topic_label && (
                  <span className="px-2 py-0.5 rounded-full border bg-purple-100 text-purple-700 border-purple-200 font-medium">
                    {mention.topic_label}
                  </span>
                )}
                {mention?.acknowledged && (
                  <span className="px-2 py-0.5 rounded-full border bg-green-100 text-green-700 border-green-200 font-medium">
                    ✓ Gestionada
                  </span>
                )}
              </div>

              {(isAnalyst || isAdmin) && mention?.id && (
                <div className="border-t border-gray-100 pt-3">
                  {!feedbackOpen ? (
                    <button
                      onClick={() => { setFeedbackOpen(true); setFeedbackLabel(mention.sentiment_label || 'neutral') }}
                      className="flex items-center gap-1.5 text-xs text-gray-400 hover:text-amber-600 transition-colors">
                      <Flag className="w-3 h-3" /> Corregir clasificación de sentimiento
                    </button>
                  ) : (
                    <div className="space-y-2">
                      <p className="text-xs font-medium text-amber-800">Corrección de sentimiento</p>
                      <select className="input text-xs py-1 w-full" value={feedbackLabel}
                        onChange={e => setFeedbackLabel(e.target.value)}>
                        <option value="positive">Positivo</option>
                        <option value="neutral">Neutral</option>
                        <option value="negative">Negativo</option>
                        <option value="very_negative">Muy negativo</option>
                      </select>
                      <input className="input text-xs py-1 w-full"
                        placeholder="Nota del analista (opcional)"
                        value={feedbackNotes} onChange={e => setFeedbackNotes(e.target.value)} />
                      <div className="flex gap-2">
                        <button className="btn-primary text-xs py-1 flex-1"
                          disabled={submitFeedback.isPending || feedbackLabel === mention.sentiment_label}
                          onClick={() => submitFeedback.mutate({ mentionId: mention.id, label: feedbackLabel, notes: feedbackNotes })}>
                          {submitFeedback.isPending ? 'Guardando…' : 'Guardar corrección'}
                        </button>
                        <button className="btn-secondary text-xs py-1"
                          onClick={() => { setFeedbackOpen(false); setFeedbackNotes('') }}>
                          Cancelar
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* Protocolo de intervención */}
            <div className="card border border-blue-100 bg-blue-50">
              <button
                onClick={() => setShowProtocol(v => !v)}
                className="w-full flex items-center justify-between text-sm font-medium text-blue-800">
                <span className="flex items-center gap-2">
                  <HelpCircle className="w-4 h-4 text-blue-500" />
                  Protocolo de intervención
                </span>
                <ChevronDown className={`w-4 h-4 text-blue-500 transition-transform ${showProtocol ? 'rotate-180' : ''}`} />
              </button>
              {showProtocol && (
                <div className="mt-3 space-y-2 text-xs text-blue-900 leading-relaxed">
                  <p className="font-semibold">Ante una mención negativa o de odio, sigue estos pasos:</p>
                  <ol className="list-decimal list-inside space-y-1.5 pl-1">
                    <li><strong>Evalúa la gravedad</strong> — ¿Es discurso de odio? ¿Amenaza directa? ¿Desinformación?</li>
                    <li><strong>Captura evidencia</strong> — Usa "Escalar a Jurídico" para guardar un snapshot antes de que sea eliminado.</li>
                    <li><strong>Reporta en la plataforma</strong> — Usa el enlace "Ver original" y reporta el contenido en la red social.</li>
                    <li><strong>Escalación jurídica</strong> — Si involucra amenazas, difamación o delitos, escala a Jurídico Iglesia o MIRA según corresponda.</li>
                    <li><strong>Reporta a autoridades</strong> — En caso de amenaza grave, reporta a Fiscalía / Policía de Colombia.</li>
                    <li><strong>Registra la acción</strong> — Guarda el tratamiento en esta bandeja para el historial de gestión.</li>
                  </ol>
                  <p className="text-blue-700 pt-1">
                    Cuentas reincidentes conocidas (Rizoma) → monitorear desde la sección <strong>Rizoma</strong> en el menú.
                  </p>
                </div>
              )}
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

            {/* Escalación jurídica */}
            {(isAdmin || isAnalyst) && mention?.id && (
              <div className="card border border-dashed border-gray-300 bg-gray-50">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-gray-700 flex items-center gap-1.5">
                      <Scale className="w-4 h-4 text-primary-600" /> Escalación jurídica
                    </p>
                    <p className="text-xs text-gray-500 mt-0.5">
                      Envía esta mención al equipo jurídico con captura de evidencia
                    </p>
                  </div>
                  <button
                    onClick={() => setShowEscalate(true)}
                    className="btn-secondary flex items-center gap-1.5 text-sm whitespace-nowrap">
                    <Scale className="w-3.5 h-3.5" /> Escalar a Jurídico
                  </button>
                </div>
              </div>
            )}

          </div>
        )}
      </div>

      {/* Modal escalación jurídica */}
      {showEscalate && mention?.id && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-md p-6 space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="font-semibold text-gray-900 flex items-center gap-2">
                <Scale className="w-5 h-5 text-primary-600" /> Escalar a equipo jurídico
              </h3>
              <button onClick={() => setShowEscalate(false)} className="text-gray-400 hover:text-gray-600">
                <X className="w-5 h-5" />
              </button>
            </div>

            <p className="text-sm text-gray-600">
              Se guardará una copia de la mención en el momento del escalamiento como evidencia.
            </p>

            <div className="space-y-2">
              <label className="label">Destino jurídico</label>
              {[
                { value: 'iglesia', label: 'Jurídico Iglesia' },
                { value: 'mira',    label: 'Jurídico MIRA' },
              ].map(opt => (
                <label key={opt.value}
                  className={`flex items-center gap-3 p-2.5 rounded-lg border cursor-pointer transition-colors ${
                    escTarget === opt.value
                      ? 'border-primary-400 bg-primary-50'
                      : 'border-gray-200 hover:border-gray-300 hover:bg-gray-50'
                  }`}>
                  <input type="radio" name="escTarget" value={opt.value}
                    checked={escTarget === opt.value}
                    onChange={() => setEscTarget(opt.value)}
                    className="accent-primary-600" />
                  <span className="text-sm text-gray-700">{opt.label}</span>
                </label>
              ))}
            </div>

            <div>
              <label className="label">Notas <span className="text-gray-400 font-normal">(opcional)</span></label>
              <textarea
                className="input resize-none"
                rows={2}
                placeholder="Contexto adicional para el equipo jurídico…"
                value={escNotes}
                onChange={e => setEscNotes(e.target.value)}
              />
            </div>

            <div className="flex gap-2 pt-1">
              <button
                onClick={() => setShowEscalate(false)}
                className="btn-secondary flex-1">
                Cancelar
              </button>
              <button
                onClick={() => escalate.mutate({ mention_id: mention.id, target: escTarget, notes: escNotes })}
                disabled={escalate.isPending || !escTarget}
                className="btn-primary flex-1">
                {escalate.isPending ? 'Escalando…' : 'Confirmar escalamiento'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
