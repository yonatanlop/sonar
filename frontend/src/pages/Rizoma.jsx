import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ShieldAlert, Twitter, Youtube, ExternalLink, ChevronLeft, ChevronRight, Flame } from 'lucide-react'
import { format } from 'date-fns'
import { es } from 'date-fns/locale'
import client from '../api/client'

const SENTIMENT_BADGE = {
  positive:      { text: 'Positivo',     cls: 'bg-green-100 text-green-700' },
  neutral:       { text: 'Neutral',      cls: 'bg-gray-100 text-gray-600' },
  negative:      { text: 'Negativo',     cls: 'bg-orange-100 text-orange-700' },
  very_negative: { text: 'Muy negativo', cls: 'bg-red-100 text-red-700' },
}

function UrgencyBadge({ score }) {
  if (score == null || score < 30) return null
  const cls =
    score >= 80 ? 'bg-red-600 text-white' :
    score >= 60 ? 'bg-red-100 text-red-700' :
                  'bg-orange-100 text-orange-700'
  return (
    <span className={`badge ${cls} flex items-center gap-1`}>
      <Flame className="w-3 h-3" /> {score.toFixed(0)}
    </span>
  )
}

export default function Rizoma() {
  const [page, setPage]       = useState(1)
  const [platform, setPlatform] = useState('')

  const { data, isLoading } = useQuery({
    queryKey: ['rizoma-feed', page, platform],
    queryFn:  () => client.get('/rizoma/feed', { params: { page, ...(platform ? { platform } : {}) } }).then(r => r.data),
  })

  const { data: sources } = useQuery({
    queryKey: ['rizoma-sources'],
    queryFn:  () => client.get('/rizoma/sources').then(r => r.data),
  })

  const twitterCount = sources?.twitter?.length ?? 0
  const youtubeCount = sources?.youtube?.length ?? 0

  return (
    <div className="space-y-4">
      {/* Cabecera */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-2">
          <ShieldAlert className="w-5 h-5 text-red-600" />
          <h1 className="text-xl font-bold text-gray-900">Rizoma</h1>
          <span className="badge bg-red-100 text-red-700 text-xs">Cuentas hostiles monitoreadas</span>
        </div>

        {/* Filtro plataforma */}
        <div className="flex gap-2">
          {[
            { value: '',        label: 'Todas' },
            { value: 'twitter', label: 'Twitter/X' },
            { value: 'youtube', label: 'YouTube' },
          ].map(opt => (
            <button
              key={opt.value}
              onClick={() => { setPlatform(opt.value); setPage(1) }}
              className={`px-3 py-1.5 rounded-lg text-sm font-medium border transition-colors ${
                platform === opt.value
                  ? 'bg-red-600 text-white border-red-600'
                  : 'bg-white text-gray-600 border-gray-200 hover:border-gray-300'
              }`}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      {/* Resumen de fuentes */}
      <div className="grid grid-cols-2 gap-3">
        <div className="card p-3 flex items-center gap-3">
          <div className="bg-sky-100 rounded-lg p-2">
            <Twitter className="w-4 h-4 text-sky-600" />
          </div>
          <div>
            <div className="text-lg font-bold text-gray-900">{twitterCount}</div>
            <div className="text-xs text-gray-500">Feeds Twitter/X</div>
          </div>
          <div className="flex-1 flex flex-wrap gap-1 justify-end">
            {(sources?.twitter ?? []).slice(0, 4).map(s => (
              <span key={s.id} className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded-full truncate max-w-[100px]">
                {s.name}
              </span>
            ))}
            {twitterCount > 4 && <span className="text-xs text-gray-400">+{twitterCount - 4}</span>}
          </div>
        </div>

        <div className="card p-3 flex items-center gap-3">
          <div className="bg-red-100 rounded-lg p-2">
            <Youtube className="w-4 h-4 text-red-600" />
          </div>
          <div>
            <div className="text-lg font-bold text-gray-900">{youtubeCount}</div>
            <div className="text-xs text-gray-500">Canales YouTube</div>
          </div>
          <div className="flex-1 flex flex-wrap gap-1 justify-end">
            {(sources?.youtube ?? []).slice(0, 4).map(s => (
              <span key={s.id} className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded-full truncate max-w-[100px]">
                {s.handle}
              </span>
            ))}
            {youtubeCount > 4 && <span className="text-xs text-gray-400">+{youtubeCount - 4}</span>}
          </div>
        </div>
      </div>

      {/* Sin fuentes Rizoma */}
      {!isLoading && twitterCount === 0 && youtubeCount === 0 && (
        <div className="card p-8 text-center text-gray-400">
          <ShieldAlert className="w-10 h-10 mx-auto mb-3 text-gray-300" />
          <p className="font-medium">No hay cuentas Rizoma configuradas</p>
          <p className="text-sm mt-1">
            Ve a Twitter Explorer o YouTube Explorer y marca cuentas hostiles con el botón Rizoma.
          </p>
        </div>
      )}

      {/* Feed de publicaciones */}
      {(twitterCount > 0 || youtubeCount > 0) && (
        <div className="card overflow-hidden">
          {isLoading ? (
            <div className="p-8 text-center text-gray-400 text-sm">Cargando publicaciones…</div>
          ) : (data?.items ?? []).length === 0 ? (
            <div className="p-8 text-center text-gray-400 text-sm">
              No hay publicaciones recientes de estas cuentas.
            </div>
          ) : (
            <div className="divide-y divide-gray-100">
              {data.items.map(item => {
                const sentiment = SENTIMENT_BADGE[item.sentiment_label]
                const isTwitter = item.source_type === 'twitter'
                return (
                  <div key={item.id} className="p-4 hover:bg-gray-50 transition-colors">
                    <div className="flex items-start gap-3">
                      {/* Icono plataforma */}
                      <div className={`rounded-full p-1.5 shrink-0 ${isTwitter ? 'bg-sky-100' : 'bg-red-100'}`}>
                        {isTwitter
                          ? <Twitter className="w-3.5 h-3.5 text-sky-600" />
                          : <Youtube className="w-3.5 h-3.5 text-red-600" />
                        }
                      </div>

                      <div className="flex-1 min-w-0">
                        {/* Meta */}
                        <div className="flex items-center gap-2 mb-1 flex-wrap">
                          <span className="text-xs font-semibold text-red-700 bg-red-50 border border-red-100 px-2 py-0.5 rounded-full">
                            {item.source_name}
                          </span>
                          {item.author_username && (
                            <span className="text-xs text-gray-500">@{item.author_username}</span>
                          )}
                          <span className="text-xs text-gray-400 ml-auto">
                            {item.published_at
                              ? format(new Date(item.published_at), 'dd MMM yyyy HH:mm', { locale: es })
                              : item.collected_at
                                ? format(new Date(item.collected_at), 'dd MMM yyyy HH:mm', { locale: es })
                                : '—'
                            }
                          </span>
                        </div>

                        {/* Contenido */}
                        <p className="text-sm text-gray-800 line-clamp-3 leading-relaxed">
                          {item.content}
                        </p>

                        {/* Badges + acciones */}
                        <div className="flex items-center gap-2 mt-2 flex-wrap">
                          {sentiment && (
                            <span className={`badge ${sentiment.cls} text-xs`}>{sentiment.text}</span>
                          )}
                          <UrgencyBadge score={item.urgency_score} />
                          {item.is_hate_speech && (
                            <span className="badge bg-red-100 text-red-700 text-xs">Odio</span>
                          )}
                          {item.url && (
                            <a
                              href={item.url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="ml-auto flex items-center gap-1 text-xs text-primary-600 hover:underline"
                            >
                              Ver original <ExternalLink className="w-3 h-3" />
                            </a>
                          )}
                        </div>
                      </div>
                    </div>
                  </div>
                )
              })}
            </div>
          )}

          {/* Paginación */}
          {data && data.pages > 1 && (
            <div className="px-4 py-3 border-t border-gray-200 flex items-center justify-between">
              <span className="text-sm text-gray-500">
                {data.total} publicaciones · página {data.page} de {data.pages}
              </span>
              <div className="flex gap-2">
                <button
                  className="btn-secondary px-3 py-1.5 text-sm flex items-center gap-1 disabled:opacity-40"
                  onClick={() => setPage(p => p - 1)}
                  disabled={page === 1}
                >
                  <ChevronLeft className="w-4 h-4" /> Anterior
                </button>
                <button
                  className="btn-secondary px-3 py-1.5 text-sm flex items-center gap-1 disabled:opacity-40"
                  onClick={() => setPage(p => p + 1)}
                  disabled={page === data.pages}
                >
                  Siguiente <ChevronRight className="w-4 h-4" />
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
