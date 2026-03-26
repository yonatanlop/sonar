import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ExternalLink, Bot, Flame, Search, SlidersHorizontal, Camera } from 'lucide-react'
import { format } from 'date-fns'
import { es } from 'date-fns/locale'
import client from '../api/client'

function UrgencyBadge({ score }) {
  if (score == null || score < 30) return null
  const cfg =
    score >= 80 ? { label: 'Crítico',  cls: 'bg-red-600 text-white' } :
    score >= 60 ? { label: 'Urgente',  cls: 'bg-red-100 text-red-700' } :
                  { label: 'Atención', cls: 'bg-orange-100 text-orange-700' }
  return (
    <span className={`badge ${cfg.cls} flex items-center gap-1`}>
      <Flame className="w-3 h-3" />
      {cfg.label} {score.toFixed(0)}
    </span>
  )
}

const fetchMentions  = (p) => {
  const params = Object.fromEntries(Object.entries(p).filter(([, v]) => v !== '' && v !== null && v !== undefined))
  return client.get('/mentions', { params }).then(r => r.data)
}
const fetchEntities       = ()      => client.get('/entities').then(r => r.data)
const fetchPlatforms      = ()      => client.get('/platforms').then(r => r.data)
const fetchSemanticSearch = (q, eid) =>
  client.get('/mentions/search', { params: { q, ...(eid ? { entity_id: eid } : {}) } }).then(r => r.data)

const PLATFORM_ICON = {
  twitter:  '🐦',
  reddit:   '🤖',
  youtube:  '▶️',
  telegram: '✈️',
  rss:      '📰',
}

export default function Mentions() {
  const [filters, setFilters] = useState({
    entity_id: '', platform: '', sentiment: '', language: '', min_urgency: '',
    exclude_duplicates: false, visual_only: false, page: 1,
  })
  const [searchMode, setSearchMode]       = useState('filters')   // 'filters' | 'semantic'
  const [semanticQuery, setSemanticQuery] = useState('')
  const [submittedQuery, setSubmittedQuery] = useState('')

  const { data, isLoading }       = useQuery({ queryKey: ['mentions', filters], queryFn: () => fetchMentions(filters), enabled: searchMode === 'filters' })
  const { data: entities = [] }   = useQuery({ queryKey: ['entities'], queryFn: fetchEntities })
  const { data: platforms = [] }  = useQuery({ queryKey: ['platforms'], queryFn: fetchPlatforms })
  const { data: semanticData, isLoading: semLoading, refetch: runSearch } = useQuery({
    queryKey: ['semantic-search', submittedQuery, filters.entity_id],
    queryFn:  () => fetchSemanticSearch(submittedQuery, filters.entity_id || null),
    enabled:  searchMode === 'semantic' && submittedQuery.length >= 3,
  })

  const setFilter = (k, v) => setFilters(f => ({ ...f, [k]: v, page: 1 }))
  const handleSemanticSearch = (e) => {
    e.preventDefault()
    if (semanticQuery.trim().length >= 3) setSubmittedQuery(semanticQuery.trim())
  }

  const MentionCard = ({ m, similarityPct }) => (
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
            {m.is_duplicate && (
              <span className="badge bg-gray-100 text-gray-500">Duplicado</span>
            )}
            {m.visual_match && (
              <span className="badge bg-green-100 text-green-700 flex items-center gap-1">
                <Camera className="w-3 h-3" />
                {m.visual_match_names
                  ? JSON.parse(m.visual_match_names).join(', ')
                  : 'Coincidencia visual'}
              </span>
            )}
            {similarityPct != null && (
              <span className="badge bg-indigo-100 text-indigo-700 ml-auto">
                <Search className="w-3 h-3 mr-1" /> {similarityPct}% similitud
              </span>
            )}
          </div>

          <p className="text-sm text-gray-700 leading-relaxed">{m.content}</p>

          <div className="flex items-center gap-3 mt-2">
            <UrgencyBadge score={m.urgency_score} />
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
  )

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Menciones</h1>
          <p className="text-gray-500 text-sm mt-0.5">Publicaciones recolectadas de redes sociales</p>
        </div>

        {/* Toggle modo */}
        <div className="flex rounded-lg border border-gray-200 overflow-hidden text-sm">
          <button
            onClick={() => setSearchMode('filters')}
            className={`px-3 py-1.5 flex items-center gap-1.5 transition-colors ${
              searchMode === 'filters'
                ? 'bg-primary-600 text-white'
                : 'bg-white text-gray-600 hover:bg-gray-50'
            }`}>
            <SlidersHorizontal className="w-3.5 h-3.5" /> Filtros
          </button>
          <button
            onClick={() => setSearchMode('semantic')}
            className={`px-3 py-1.5 flex items-center gap-1.5 transition-colors ${
              searchMode === 'semantic'
                ? 'bg-primary-600 text-white'
                : 'bg-white text-gray-600 hover:bg-gray-50'
            }`}>
            <Search className="w-3.5 h-3.5" /> Búsqueda semántica
          </button>
        </div>
      </div>

      {searchMode === 'filters' ? (
        <>
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

              <select className="input w-auto" value={filters.min_urgency}
                onChange={e => setFilter('min_urgency', e.target.value)}>
                <option value="">Todas las urgencias</option>
                <option value="30">🟠 Media o mayor (≥30)</option>
                <option value="60">🔴 Alta o mayor (≥60)</option>
                <option value="80">🔥 Solo críticas (≥80)</option>
              </select>

              <div className="flex items-center gap-4 ml-auto flex-wrap">
                <label className="flex items-center gap-2 cursor-pointer select-none">
                  <span className="text-xs text-gray-600">Ocultar duplicados</span>
                  <button
                    type="button" role="switch"
                    aria-checked={filters.exclude_duplicates}
                    onClick={() => setFilter('exclude_duplicates', !filters.exclude_duplicates)}
                    className={`relative inline-flex h-5 w-9 shrink-0 rounded-full border-2 border-transparent transition-colors ${
                      filters.exclude_duplicates ? 'bg-primary-600' : 'bg-gray-200'
                    }`}>
                    <span className={`pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition-transform ${
                      filters.exclude_duplicates ? 'translate-x-4' : 'translate-x-0'
                    }`} />
                  </button>
                </label>
                <label className="flex items-center gap-2 cursor-pointer select-none">
                  <Camera className="w-3.5 h-3.5 text-green-600" />
                  <span className="text-xs text-gray-600">Solo visuales</span>
                  <button
                    type="button" role="switch"
                    aria-checked={filters.visual_only}
                    onClick={() => setFilter('visual_only', !filters.visual_only)}
                    className={`relative inline-flex h-5 w-9 shrink-0 rounded-full border-2 border-transparent transition-colors ${
                      filters.visual_only ? 'bg-green-600' : 'bg-gray-200'
                    }`}>
                    <span className={`pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition-transform ${
                      filters.visual_only ? 'translate-x-4' : 'translate-x-0'
                    }`} />
                  </button>
                </label>
              </div>
            </div>
          </div>

          <div className="text-xs text-gray-400">
            {data?.total ? `${data.total.toLocaleString()} menciones encontradas` : ''}
          </div>

          {isLoading ? (
            <div className="text-center text-gray-400 py-12">Cargando menciones...</div>
          ) : (
            <div className="space-y-3">
              {data?.items?.map(m => <MentionCard key={m.id} m={m} />)}
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
        </>
      ) : (
        <>
          {/* Búsqueda semántica */}
          <div className="card py-4">
            <form onSubmit={handleSemanticSearch} className="flex flex-col gap-3">
              <p className="text-xs text-gray-500">
                Busca menciones por significado, no solo por palabras clave exactas.
                Requiere que los embeddings estén generados (cada 30 min vía tarea automática).
              </p>
              <div className="flex gap-2 flex-wrap">
                <select className="input w-auto" value={filters.entity_id}
                  onChange={e => setFilter('entity_id', e.target.value)}>
                  <option value="">Todas las entidades</option>
                  {entities.map(e => <option key={e.id} value={e.id}>{e.name}</option>)}
                </select>
                <div className="flex flex-1 min-w-64 gap-2">
                  <input
                    className="input flex-1"
                    placeholder='Ej: "críticas al servicio al cliente"'
                    value={semanticQuery}
                    onChange={e => setSemanticQuery(e.target.value)}
                  />
                  <button type="submit"
                    disabled={semanticQuery.trim().length < 3}
                    className="btn-primary flex items-center gap-1.5">
                    <Search className="w-4 h-4" /> Buscar
                  </button>
                </div>
              </div>
            </form>
          </div>

          {semLoading && (
            <div className="text-center text-gray-400 py-12">Buscando menciones similares...</div>
          )}

          {semanticData && !semLoading && (
            <>
              <div className="text-xs text-gray-400">
                {semanticData.results?.length
                  ? `${semanticData.results.length} menciones similares a "${semanticData.query}"`
                  : semanticData.note
                    ? `Sin resultados — ${semanticData.note}`
                    : `Sin menciones similares para "${semanticData.query}"`}
              </div>
              <div className="space-y-3">
                {semanticData.results?.map(r => (
                  <MentionCard
                    key={r.id}
                    m={r}
                    similarityPct={r.similarity != null ? Math.round(r.similarity * 100) : null}
                  />
                ))}
              </div>
            </>
          )}

          {!semLoading && !semanticData && submittedQuery === '' && (
            <div className="text-center text-gray-300 py-16">
              <Search className="w-10 h-10 mx-auto mb-3 opacity-40" />
              <p className="text-sm">Escribe una consulta para buscar menciones por similitud semántica</p>
            </div>
          )}
        </>
      )}
    </div>
  )
}
