import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ExternalLink, Bot } from 'lucide-react'
import { format } from 'date-fns'
import { es } from 'date-fns/locale'
import client from '../api/client'

const fetchMentions  = (p) => {
  // Omitir parámetros vacíos para evitar errores de validación en el backend
  const params = Object.fromEntries(Object.entries(p).filter(([, v]) => v !== '' && v !== null && v !== undefined))
  return client.get('/mentions', { params }).then(r => r.data)
}
const fetchEntities  = ()  => client.get('/entities').then(r => r.data)
const fetchPlatforms = ()  => client.get('/platforms').then(r => r.data)

const PLATFORM_ICON = {
  twitter:  '🐦',
  reddit:   '🤖',
  youtube:  '▶️',
  telegram: '✈️',
  rss:      '📰',
}

export default function Mentions() {
  const [filters, setFilters] = useState({
    entity_id: '', platform: '', sentiment: '', language: '', page: 1,
  })

  const { data, isLoading }     = useQuery({ queryKey: ['mentions', filters], queryFn: () => fetchMentions(filters) })
  const { data: entities = [] } = useQuery({ queryKey: ['entities'], queryFn: fetchEntities })
  const { data: platforms = [] } = useQuery({ queryKey: ['platforms'], queryFn: fetchPlatforms })

  const setFilter = (k, v) => setFilters(f => ({ ...f, [k]: v, page: 1 }))

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Menciones</h1>
        <p className="text-gray-500 text-sm mt-0.5">Publicaciones recolectadas de redes sociales</p>
      </div>

      {/* Filtros */}
      <div className="card py-4">
        <div className="flex flex-wrap gap-3">
          <select className="input w-auto" value={filters.entity_id}
            onChange={e => setFilter('entity_id', e.target.value)}>
            <option value="">Todas las entidades</option>
            {entities.map(e => <option key={e.id} value={e.id}>{e.name}</option>)}
          </select>

          <select className="input w-auto" value={filters.platform}
            onChange={e => setFilter('platform', e.target.value)}>
            <option value="">Todas las plataformas</option>
            {platforms.map(p => <option key={p.code} value={p.code}>{p.name}</option>)}
          </select>

          <select className="input w-auto" value={filters.sentiment}
            onChange={e => setFilter('sentiment', e.target.value)}>
            <option value="">Todos los sentimientos</option>
            <option value="very_negative">Muy negativo</option>
            <option value="negative">Negativo</option>
            <option value="neutral">Neutral</option>
            <option value="positive">Positivo</option>
          </select>

          <select className="input w-auto" value={filters.language}
            onChange={e => setFilter('language', e.target.value)}>
            <option value="">Todos los idiomas</option>
            <option value="es">Español</option>
            <option value="en">Inglés</option>
          </select>
        </div>
      </div>

      {/* Resultados */}
      <div className="text-xs text-gray-400">
        {data?.total ? `${data.total.toLocaleString()} menciones encontradas` : ''}
      </div>

      {isLoading ? (
        <div className="text-center text-gray-400 py-12">Cargando menciones...</div>
      ) : (
        <div className="space-y-3">
          {data?.items?.map(m => (
            <div key={m.id} className="card py-4">
              <div className="flex items-start gap-3">
                <span className="text-xl shrink-0 mt-0.5">{PLATFORM_ICON[m.platform_code] ?? '🌐'}</span>

                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap mb-1">
                    <span className="font-medium text-sm text-gray-800">@{m.author_username}</span>
                    <span className="text-gray-300">·</span>
                    <span className="text-xs text-gray-400">{m.platform_name}</span>
                    <span className="text-gray-300">·</span>
                    <span className="text-xs text-gray-400">
                      {format(new Date(m.published_at), "d MMM yyyy, HH:mm", { locale: es })}
                    </span>
                    {m.is_bot && (
                      <span className="badge bg-purple-100 text-purple-700">
                        <Bot className="w-3 h-3 mr-1" /> BOT
                      </span>
                    )}
                  </div>

                  <p className="text-sm text-gray-700 leading-relaxed">{m.content}</p>

                  <div className="flex items-center gap-3 mt-2">
                    <span className={`badge badge-${m.sentiment_label}`}>
                      {m.sentiment_label?.replace('_', ' ') ?? '—'}
                    </span>
                    {m.is_hate_speech && (
                      <span className="badge bg-red-100 text-red-700">Discurso de odio</span>
                    )}
                    <span className="text-xs text-gray-400">{m.entity_name}</span>
                    {m.reach > 0 && (
                      <span className="text-xs text-gray-400 ml-auto">
                        👍 {m.reach.toLocaleString()} interacciones
                      </span>
                    )}
                    {m.url && (
                      <a href={m.url} target="_blank" rel="noopener noreferrer"
                        className="text-primary-600 hover:text-primary-800 ml-auto">
                        <ExternalLink className="w-3.5 h-3.5" />
                      </a>
                    )}
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Paginación */}
      {data?.total > 20 && (
        <div className="flex justify-center gap-2">
          <button disabled={filters.page === 1}
            onClick={() => setFilters(f => ({ ...f, page: f.page - 1 }))}
            className="btn-secondary text-sm">← Anterior</button>
          <span className="text-sm text-gray-500 self-center">
            Página {filters.page} de {Math.ceil(data.total / 20)}
          </span>
          <button disabled={filters.page >= Math.ceil(data.total / 20)}
            onClick={() => setFilters(f => ({ ...f, page: f.page + 1 }))}
            className="btn-secondary text-sm">Siguiente →</button>
        </div>
      )}
    </div>
  )
}
