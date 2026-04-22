import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { format } from 'date-fns'
import { es } from 'date-fns/locale'
import client from '../../../shared/api/client'

const PLATFORM_ICON = { twitter: '🐦', reddit: '🤖', youtube: '▶️', rss: '📰', instagram: '📸', facebook: '👥' }

const fetchMentions = (p) => {
  const params = Object.fromEntries(Object.entries(p).filter(([, v]) => v !== ''))
  return client.get('/mentions', { params }).then(r => r.data)
}

export default function Mentions() {
  const [filters, setFilters] = useState({ sentiment: '', platform: '', page: 1, page_size: 25 })
  const setFilter = (k, v) => setFilters(f => ({ ...f, [k]: v, page: 1 }))

  const { data, isLoading } = useQuery({
    queryKey: ['mentions', filters],
    queryFn: () => fetchMentions(filters),
  })

  const mentions = data?.items ?? data ?? []

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Menciones</h1>
        <p className="text-gray-500 text-sm mt-0.5">Menciones recopiladas de todas las plataformas</p>
      </div>

      <div className="card py-4">
        <div className="flex flex-wrap gap-3">
          <select className="input w-auto" value={filters.sentiment} onChange={e => setFilter('sentiment', e.target.value)}>
            <option value="">Todos los sentimientos</option>
            <option value="positive">Positivo</option>
            <option value="neutral">Neutral</option>
            <option value="negative">Negativo</option>
            <option value="very_negative">Muy negativo</option>
          </select>
          <select className="input w-auto" value={filters.platform} onChange={e => setFilter('platform', e.target.value)}>
            <option value="">Todas las plataformas</option>
            {['twitter','reddit','youtube','rss','instagram','facebook'].map(p => (
              <option key={p} value={p}>{PLATFORM_ICON[p]} {p}</option>
            ))}
          </select>
        </div>
      </div>

      {isLoading ? (
        <div className="text-center text-gray-400 py-12">Cargando menciones...</div>
      ) : (
        <div className="space-y-3">
          {mentions.map(m => (
            <div key={m.id} className="card p-4">
              <div className="flex items-start gap-3">
                <span className="text-xl">{PLATFORM_ICON[m.platform] ?? '🌐'}</span>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap mb-1">
                    <span className="font-medium text-gray-900 text-sm truncate">{m.author ?? 'Anónimo'}</span>
                    <span className={`badge badge-${m.sentiment ?? 'neutral'}`}>
                      {m.sentiment ?? 'sin analizar'}
                    </span>
                    {m.is_bot && <span className="badge badge-high">BOT</span>}
                    <span className="text-xs text-gray-400 ml-auto">
                      {format(new Date(m.published_at), "d MMM yyyy HH:mm", { locale: es })}
                    </span>
                  </div>
                  <p className="text-sm text-gray-700 line-clamp-3">{m.content}</p>
                  {m.url && (
                    <a href={m.url} target="_blank" rel="noreferrer"
                      className="text-xs text-primary-600 hover:underline mt-1 block truncate">
                      {m.url}
                    </a>
                  )}
                </div>
              </div>
            </div>
          ))}
          {mentions.length === 0 && (
            <div className="text-center text-gray-400 py-12">No hay menciones con los filtros seleccionados</div>
          )}
        </div>
      )}

      {data?.total > filters.page_size && (
        <div className="flex justify-center gap-2">
          <button className="btn-secondary" disabled={filters.page <= 1}
            onClick={() => setFilters(f => ({ ...f, page: f.page - 1 }))}>
            ← Anterior
          </button>
          <span className="flex items-center text-sm text-gray-500">
            Página {filters.page}
          </span>
          <button className="btn-secondary"
            disabled={filters.page * filters.page_size >= data.total}
            onClick={() => setFilters(f => ({ ...f, page: f.page + 1 }))}>
            Siguiente →
          </button>
        </div>
      )}
    </div>
  )
}
