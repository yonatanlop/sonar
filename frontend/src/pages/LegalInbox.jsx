import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Scale, CheckCircle, Clock, Globe, User, ExternalLink,
  ChevronLeft, ChevronRight,
} from 'lucide-react'
import toast from 'react-hot-toast'
import client from '../api/client'

const TARGET_BADGE = {
  iglesia: { text: 'Iglesia', cls: 'bg-blue-100 text-blue-700 border-blue-200' },
  mira:    { text: 'MIRA',    cls: 'bg-purple-100 text-purple-700 border-purple-200' },
}

function timeAgo(isoStr) {
  if (!isoStr) return '—'
  const diff = Math.floor((Date.now() - new Date(isoStr)) / 1000)
  if (diff < 60)    return 'hace un momento'
  if (diff < 3600)  return `hace ${Math.floor(diff / 60)} min`
  if (diff < 86400) return `hace ${Math.floor(diff / 3600)} h`
  return `hace ${Math.floor(diff / 86400)} d`
}

export default function LegalInbox() {
  const qc = useQueryClient()
  const [target, setTarget]   = useState('')
  const [pending, setPending] = useState(null)
  const [page, setPage]       = useState(1)

  const params = { page }
  if (target)       params.target  = target
  if (pending !== null) params.pending = pending

  const { data, isLoading } = useQuery({
    queryKey: ['legal-escalations', params],
    queryFn:  () => client.get('/legal/escalations', { params }).then(r => r.data),
    refetchInterval: 30_000,
  })

  const receive = useMutation({
    mutationFn: (id) => client.patch(`/legal/escalations/${id}/receive`),
    onSuccess: () => {
      toast.success('Marcado como recibido')
      qc.invalidateQueries({ queryKey: ['legal-escalations'] })
    },
    onError: (err) => {
      toast.error(err?.response?.data?.detail ?? 'Error al actualizar')
    },
  })

  const items      = data?.items      ?? []
  const totalPages = data?.pages      ?? 1

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <div className="flex items-center gap-2 mb-1">
          <Scale className="w-5 h-5 text-primary-600" />
          <h1 className="text-xl font-bold text-gray-900">Bandeja jurídica</h1>
        </div>
        <p className="text-sm text-gray-500">
          Menciones escaladas al equipo jurídico para seguimiento formal
        </p>
      </div>

      {/* Filtros */}
      <div className="card flex flex-wrap gap-3 items-center">
        <span className="text-sm font-medium text-gray-700">Destino:</span>
        <div className="flex gap-1">
          {[
            { value: '',        label: 'Todos' },
            { value: 'iglesia', label: 'Iglesia' },
            { value: 'mira',    label: 'MIRA' },
          ].map(opt => (
            <button key={opt.value}
              onClick={() => { setTarget(opt.value); setPage(1) }}
              className={`px-3 py-1 rounded-full text-sm border transition-colors ${
                target === opt.value
                  ? 'bg-primary-600 text-white border-primary-600'
                  : 'border-gray-200 text-gray-600 hover:border-primary-400'
              }`}>
              {opt.label}
            </button>
          ))}
        </div>

        <span className="text-sm font-medium text-gray-700 ml-2">Estado:</span>
        <div className="flex gap-1">
          {[
            { value: null,  label: 'Todos' },
            { value: true,  label: 'Pendientes' },
            { value: false, label: 'Recibidos' },
          ].map(opt => (
            <button key={String(opt.value)}
              onClick={() => { setPending(opt.value); setPage(1) }}
              className={`px-3 py-1 rounded-full text-sm border transition-colors ${
                pending === opt.value
                  ? 'bg-primary-600 text-white border-primary-600'
                  : 'border-gray-200 text-gray-600 hover:border-primary-400'
              }`}>
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      {/* Lista */}
      {isLoading ? (
        <div className="text-center text-gray-400 py-16 text-sm">Cargando casos jurídicos…</div>
      ) : items.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-16 text-gray-400 gap-3">
          <CheckCircle className="w-10 h-10 text-green-400" />
          <p className="text-sm font-medium">No hay casos que mostrar</p>
          <p className="text-xs">Ajusta los filtros o espera nuevos escalamientos</p>
        </div>
      ) : (
        <div className="space-y-3">
          {items.map(item => {
            const snap       = item.snapshot ?? {}
            const badge      = TARGET_BADGE[item.target]
            const isReceived = !!item.received_at
            return (
              <div key={item.id} className={`card border-l-4 ${
                isReceived ? 'border-green-400' : 'border-orange-400'
              }`}>
                {/* Cabecera */}
                <div className="flex flex-wrap items-start justify-between gap-3 mb-3">
                  <div className="flex items-center gap-2 flex-wrap">
                    {badge && (
                      <span className={`px-2.5 py-0.5 rounded-full text-xs font-semibold border ${badge.cls}`}>
                        {badge.text}
                      </span>
                    )}
                    {isReceived ? (
                      <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold border bg-green-100 text-green-700 border-green-200 flex items-center gap-1">
                        <CheckCircle className="w-3 h-3" /> Recibido
                      </span>
                    ) : (
                      <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold border bg-orange-100 text-orange-700 border-orange-200 flex items-center gap-1">
                        <Clock className="w-3 h-3" /> Pendiente
                      </span>
                    )}
                  </div>
                  <span className="text-xs text-gray-400 flex items-center gap-1">
                    <Clock className="w-3 h-3" /> {timeAgo(item.escalated_at)}
                  </span>
                </div>

                {/* Contenido del snapshot */}
                <p className="text-sm text-gray-800 leading-relaxed border-l-2 border-gray-200 pl-3 mb-3 whitespace-pre-wrap">
                  {snap.content ?? '— contenido no disponible —'}
                </p>

                {/* Meta */}
                <div className="flex flex-wrap gap-4 text-xs text-gray-500 mb-3">
                  {snap.author_username && (
                    <span className="flex items-center gap-1">
                      <User className="w-3 h-3" /> @{snap.author_username}
                    </span>
                  )}
                  {snap.platform_code && (
                    <span className="flex items-center gap-1">
                      <Globe className="w-3 h-3" /> {snap.platform_code}
                    </span>
                  )}
                  {snap.url && (
                    <a href={snap.url} target="_blank" rel="noopener noreferrer"
                       className="flex items-center gap-1 text-primary-600 hover:underline">
                      <ExternalLink className="w-3 h-3" /> Ver original
                    </a>
                  )}
                </div>

                {/* Pie */}
                <div className="flex items-center justify-between pt-2 border-t border-gray-100 gap-2">
                  <p className="text-xs text-gray-400">
                    Escalado por{' '}
                    <span className="font-medium text-gray-600">
                      {item.escalated_by?.full_name ?? '—'}
                    </span>
                    {isReceived && item.received_by && (
                      <>
                        {' · '}Recibido por{' '}
                        <span className="font-medium text-gray-600">
                          {item.received_by.full_name}
                        </span>
                        {' '}{timeAgo(item.received_at)}
                      </>
                    )}
                  </p>
                  {!isReceived && (
                    <button
                      onClick={() => receive.mutate(item.id)}
                      disabled={receive.isPending}
                      className="btn-primary text-sm py-1.5 px-3 flex items-center gap-1.5 shrink-0">
                      <CheckCircle className="w-3.5 h-3.5" /> Marcar recibido
                    </button>
                  )}
                </div>

                {item.notes && (
                  <p className="mt-2 text-xs text-gray-500 italic border-t border-gray-100 pt-2">
                    Notas: {item.notes}
                  </p>
                )}
              </div>
            )
          })}
        </div>
      )}

      {/* Paginación */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-3">
          <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1}
                  className="btn-secondary p-2 disabled:opacity-40">
            <ChevronLeft className="w-4 h-4" />
          </button>
          <span className="text-sm text-gray-600">{page} / {totalPages}</span>
          <button onClick={() => setPage(p => Math.min(totalPages, p + 1))} disabled={page === totalPages}
                  className="btn-secondary p-2 disabled:opacity-40">
            <ChevronRight className="w-4 h-4" />
          </button>
        </div>
      )}
    </div>
  )
}
