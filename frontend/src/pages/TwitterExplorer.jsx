/**
 * Twitter Explorer — Monitoreo de @usuarios, #hashtags y palabras clave
 * Panel izquierdo: lista de feeds activos
 * Panel derecho: tweets del feed seleccionado con filtros
 */
import { useState, useEffect, useCallback } from 'react'
import {
  Twitter, Plus, Trash2, ChevronRight, RefreshCw,
  Calendar, Filter, ExternalLink, User, Hash, Search,
} from 'lucide-react'
import api from '../api/client'

// ── Tweet Card ────────────────────────────────────────────────────────────────

function TweetCard({ mention }) {
  const date = mention.published_at
    ? new Date(mention.published_at).toLocaleString('es-CO', {
        day: '2-digit', month: 'short', year: 'numeric',
        hour: '2-digit', minute: '2-digit',
      })
    : '—'

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-4 hover:shadow-md transition-shadow">
      {/* Cabecera */}
      <div className="flex items-start justify-between gap-2 mb-2">
        <div className="flex items-center gap-2 min-w-0">
          <div className="bg-sky-100 rounded-full p-1.5 shrink-0">
            <User className="w-3.5 h-3.5 text-sky-500" />
          </div>
          <span className="font-medium text-sm text-gray-800 truncate">
            {mention.author_username ? `@${mention.author_username}` : 'Desconocido'}
          </span>
        </div>
        {mention.url && (
          <a
            href={mention.url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-gray-400 hover:text-sky-500 transition-colors shrink-0"
            title="Ver tweet original"
          >
            <ExternalLink className="w-3.5 h-3.5" />
          </a>
        )}
      </div>

      {/* Contenido */}
      <p className="text-sm text-gray-700 leading-relaxed line-clamp-4">{mention.content}</p>

      {/* Footer */}
      <div className="flex items-center justify-between mt-3 text-xs text-gray-400">
        <span className="flex items-center gap-1">
          <Calendar className="w-3 h-3" /> {date}
        </span>
        <div className="flex items-center gap-3">
          {mention.reach > 0 && (
            <span>❤️ {mention.reach.toLocaleString()}</span>
          )}
          {mention.language && (
            <span className="uppercase font-mono">{mention.language}</span>
          )}
        </div>
      </div>
    </div>
  )
}

// ── Feed Item (panel izquierdo) ───────────────────────────────────────────────

function FeedItem({ feed, selected, onClick, onDelete }) {
  const Icon = feed.feed_type === 'user' ? User : feed.feed_type === 'hashtag' ? Hash : Search

  return (
    <div
      className={`flex items-center gap-2 px-3 py-2.5 rounded-lg cursor-pointer group transition-colors ${
        selected ? 'bg-sky-50 border border-sky-200' : 'hover:bg-gray-50 border border-transparent'
      }`}
      onClick={onClick}
    >
      <div className={`rounded-full p-1 ${selected ? 'bg-sky-100' : 'bg-gray-100'}`}>
        <Icon className={`w-3 h-3 ${selected ? 'text-sky-600' : 'text-gray-500'}`} />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-gray-800 truncate">{feed.display_name}</p>
        <p className="text-xs text-gray-400">{feed.mention_count} tweets</p>
      </div>
      <button
        onClick={(e) => { e.stopPropagation(); onDelete(feed.id) }}
        className="opacity-0 group-hover:opacity-100 text-gray-300 hover:text-red-500 transition-all"
        title="Eliminar feed"
      >
        <Trash2 className="w-3.5 h-3.5" />
      </button>
      {selected && <ChevronRight className="w-3.5 h-3.5 text-sky-400 shrink-0" />}
    </div>
  )
}

// ── Add Feed Modal ────────────────────────────────────────────────────────────

function AddFeedModal({ onClose, onAdded }) {
  const [feedType, setFeedType] = useState('user')
  const [term, setTerm]         = useState('')
  const [loading, setLoading]   = useState(false)
  const [error, setError]       = useState('')

  const placeholder = feedType === 'user' ? '@pepito (sin @)' : feedType === 'hashtag' ? '#MIRA (sin #)' : 'elecciones 2026'

  async function handleSubmit(e) {
    e.preventDefault()
    if (!term.trim()) return
    setLoading(true)
    setError('')
    try {
      const { data } = await api.post('/twitter-feeds', { feed_type: feedType, term: term.trim() })
      onAdded(data)
      onClose()
    } catch (err) {
      setError(err.response?.data?.detail || 'Error al agregar el feed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4" onClick={onClose}>
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-md p-6" onClick={(e) => e.stopPropagation()}>
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Agregar monitor</h3>

        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Tipo */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5">Tipo</label>
            <div className="flex gap-2">
              {[
                { value: 'user',    icon: User,   label: 'Usuario' },
                { value: 'hashtag', icon: Hash,   label: 'Hashtag' },
                { value: 'keyword', icon: Search, label: 'Palabra clave' },
              ].map(({ value, icon: Icon, label }) => (
                <button
                  key={value}
                  type="button"
                  onClick={() => setFeedType(value)}
                  className={`flex-1 flex flex-col items-center gap-1 py-2.5 rounded-lg border text-xs font-medium transition-colors ${
                    feedType === value
                      ? 'bg-sky-50 border-sky-400 text-sky-700'
                      : 'border-gray-200 text-gray-500 hover:bg-gray-50'
                  }`}
                >
                  <Icon className="w-4 h-4" />
                  {label}
                </button>
              ))}
            </div>
          </div>

          {/* Término */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5">
              {feedType === 'user' ? 'Nombre de usuario' : feedType === 'hashtag' ? 'Hashtag' : 'Palabra o frase'}
            </label>
            <input
              type="text"
              value={term}
              onChange={(e) => setTerm(e.target.value)}
              placeholder={placeholder}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-sky-400"
              autoFocus
            />
          </div>

          {error && <p className="text-sm text-red-600">{error}</p>}

          <div className="flex gap-2 pt-1">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 px-4 py-2 border border-gray-300 rounded-lg text-sm text-gray-600 hover:bg-gray-50"
            >
              Cancelar
            </button>
            <button
              type="submit"
              disabled={loading || !term.trim()}
              className="flex-1 px-4 py-2 bg-sky-500 text-white rounded-lg text-sm font-medium hover:bg-sky-600 disabled:opacity-50"
            >
              {loading ? 'Agregando...' : 'Agregar'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

// ── Main Page ─────────────────────────────────────────────────────────────────

export default function TwitterExplorer() {
  const [feeds, setFeeds]             = useState([])
  const [selectedFeed, setSelectedFeed] = useState(null)
  const [mentions, setMentions]       = useState([])
  const [total, setTotal]             = useState(0)
  const [page, setPage]               = useState(1)
  const [pages, setPages]             = useState(1)
  const [loadingFeeds, setLoadingFeeds] = useState(true)
  const [loadingMentions, setLoadingMentions] = useState(false)
  const [showModal, setShowModal]     = useState(false)

  // Filtros
  const [dateFrom, setDateFrom]       = useState('')
  const [dateTo, setDateTo]           = useState('')

  // Agrupación visual
  const users    = feeds.filter((f) => f.feed_type === 'user')
  const hashtags = feeds.filter((f) => f.feed_type === 'hashtag')
  const keywords = feeds.filter((f) => f.feed_type === 'keyword')

  // ── Cargar feeds ──────────────────────────────────────────────
  const loadFeeds = useCallback(async () => {
    setLoadingFeeds(true)
    try {
      const { data } = await api.get('/twitter-feeds')
      setFeeds(data)
    } finally {
      setLoadingFeeds(false)
    }
  }, [])

  useEffect(() => { loadFeeds() }, [loadFeeds])

  // ── Cargar menciones ──────────────────────────────────────────
  const loadMentions = useCallback(async (feedId, pg = 1) => {
    if (!feedId) return
    setLoadingMentions(true)
    try {
      const params = { page: pg }
      if (dateFrom) params.date_from = dateFrom
      if (dateTo)   params.date_to   = dateTo
      const { data } = await api.get(`/twitter-feeds/${feedId}/mentions`, { params })
      setMentions(data.mentions)
      setTotal(data.total)
      setPage(data.page)
      setPages(data.pages)
    } finally {
      setLoadingMentions(false)
    }
  }, [dateFrom, dateTo])

  useEffect(() => {
    if (selectedFeed) loadMentions(selectedFeed.id, 1)
  }, [selectedFeed, dateFrom, dateTo, loadMentions])

  // ── Handlers ──────────────────────────────────────────────────
  function handleSelectFeed(feed) {
    setSelectedFeed(feed)
    setPage(1)
    setMentions([])
  }

  async function handleDeleteFeed(feedId) {
    if (!confirm('¿Eliminar este monitor? No se borrarán los tweets ya recolectados.')) return
    await api.delete(`/twitter-feeds/${feedId}`)
    setFeeds((prev) => prev.filter((f) => f.id !== feedId))
    if (selectedFeed?.id === feedId) {
      setSelectedFeed(null)
      setMentions([])
    }
  }

  function handleFeedAdded(feed) {
    setFeeds((prev) => [...prev, feed])
    setSelectedFeed(feed)
  }

  function resetFilters() {
    setDateFrom('')
    setDateTo('')
  }

  // ── Render ────────────────────────────────────────────────────
  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <div className="bg-sky-100 rounded-lg p-2">
            <Twitter className="w-5 h-5 text-sky-500" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-gray-900">Twitter Explorer</h1>
            <p className="text-xs text-gray-500">Monitorea cuentas, hashtags y palabras clave en tiempo real</p>
          </div>
        </div>
        <button
          onClick={() => setShowModal(true)}
          className="flex items-center gap-1.5 bg-sky-500 hover:bg-sky-600 text-white px-3 py-2 rounded-lg text-sm font-medium transition-colors"
        >
          <Plus className="w-4 h-4" /> Agregar monitor
        </button>
      </div>

      {/* Cuerpo: panel dividido */}
      <div className="flex-1 flex gap-4 min-h-0">

        {/* ── Panel izquierdo: lista de feeds ── */}
        <div className="w-64 shrink-0 bg-white rounded-xl border border-gray-200 flex flex-col overflow-hidden">
          <div className="px-3 py-2.5 border-b border-gray-100 flex items-center justify-between">
            <span className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Monitores</span>
            <button onClick={loadFeeds} className="text-gray-400 hover:text-gray-600" title="Actualizar lista">
              <RefreshCw className="w-3.5 h-3.5" />
            </button>
          </div>

          <div className="flex-1 overflow-y-auto p-2 space-y-3">
            {loadingFeeds ? (
              <p className="text-xs text-gray-400 text-center pt-4">Cargando...</p>
            ) : feeds.length === 0 ? (
              <div className="text-center pt-6 px-3">
                <Twitter className="w-8 h-8 text-gray-200 mx-auto mb-2" />
                <p className="text-xs text-gray-400">Sin monitores aún.</p>
                <button
                  onClick={() => setShowModal(true)}
                  className="mt-2 text-xs text-sky-500 hover:underline"
                >
                  + Agregar primero
                </button>
              </div>
            ) : (
              <>
                {users.length > 0 && (
                  <div>
                    <p className="text-xs text-gray-400 px-3 mb-1 font-medium">Usuarios</p>
                    {users.map((f) => (
                      <FeedItem
                        key={f.id}
                        feed={f}
                        selected={selectedFeed?.id === f.id}
                        onClick={() => handleSelectFeed(f)}
                        onDelete={handleDeleteFeed}
                      />
                    ))}
                  </div>
                )}
                {hashtags.length > 0 && (
                  <div>
                    <p className="text-xs text-gray-400 px-3 mb-1 font-medium">Hashtags</p>
                    {hashtags.map((f) => (
                      <FeedItem
                        key={f.id}
                        feed={f}
                        selected={selectedFeed?.id === f.id}
                        onClick={() => handleSelectFeed(f)}
                        onDelete={handleDeleteFeed}
                      />
                    ))}
                  </div>
                )}
                {keywords.length > 0 && (
                  <div>
                    <p className="text-xs text-gray-400 px-3 mb-1 font-medium">Palabras clave</p>
                    {keywords.map((f) => (
                      <FeedItem
                        key={f.id}
                        feed={f}
                        selected={selectedFeed?.id === f.id}
                        onClick={() => handleSelectFeed(f)}
                        onDelete={handleDeleteFeed}
                      />
                    ))}
                  </div>
                )}
              </>
            )}
          </div>
        </div>

        {/* ── Panel derecho: tweets ── */}
        <div className="flex-1 flex flex-col min-w-0">
          {!selectedFeed ? (
            <div className="flex-1 flex items-center justify-center bg-white rounded-xl border border-gray-200">
              <div className="text-center">
                <Twitter className="w-12 h-12 text-gray-200 mx-auto mb-3" />
                <p className="text-gray-400 text-sm">Selecciona un monitor para ver sus tweets</p>
              </div>
            </div>
          ) : (
            <>
              {/* Barra de filtros */}
              <div className="bg-white rounded-xl border border-gray-200 px-4 py-3 mb-3 flex flex-wrap items-center gap-3">
                <div className="flex items-center gap-1.5 text-sm font-semibold text-gray-700">
                  <Twitter className="w-4 h-4 text-sky-500" />
                  {selectedFeed.display_name}
                  <span className="text-xs text-gray-400 font-normal">({total} tweets)</span>
                </div>
                <div className="ml-auto flex flex-wrap items-center gap-2">
                  <Filter className="w-3.5 h-3.5 text-gray-400" />
                  <input
                    type="date"
                    value={dateFrom}
                    onChange={(e) => setDateFrom(e.target.value)}
                    className="text-xs border border-gray-200 rounded-lg px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-sky-300"
                    placeholder="Desde"
                  />
                  <input
                    type="date"
                    value={dateTo}
                    onChange={(e) => setDateTo(e.target.value)}
                    className="text-xs border border-gray-200 rounded-lg px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-sky-300"
                    placeholder="Hasta"
                  />
                  {(dateFrom || dateTo) && (
                    <button
                      onClick={resetFilters}
                      className="text-xs text-sky-500 hover:underline"
                    >
                      Limpiar
                    </button>
                  )}
                  <button
                    onClick={() => loadMentions(selectedFeed.id, page)}
                    className="text-gray-400 hover:text-sky-500 transition-colors"
                    title="Actualizar"
                  >
                    <RefreshCw className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>

              {/* Lista de tweets */}
              <div className="flex-1 overflow-y-auto space-y-3">
                {loadingMentions ? (
                  <div className="flex items-center justify-center pt-12">
                    <RefreshCw className="w-5 h-5 text-sky-400 animate-spin" />
                  </div>
                ) : mentions.length === 0 ? (
                  <div className="flex flex-col items-center justify-center pt-12 text-center">
                    <Twitter className="w-10 h-10 text-gray-200 mb-3" />
                    <p className="text-gray-400 text-sm">Sin tweets aún.</p>
                    <p className="text-gray-400 text-xs mt-1">
                      El scraper recolecta datos cada 20 minutos.
                    </p>
                  </div>
                ) : (
                  <>
                    {mentions.map((m) => <TweetCard key={m.id} mention={m} />)}

                    {/* Paginación */}
                    {pages > 1 && (
                      <div className="flex items-center justify-center gap-2 pt-2 pb-4">
                        <button
                          onClick={() => loadMentions(selectedFeed.id, page - 1)}
                          disabled={page <= 1}
                          className="px-3 py-1.5 text-xs border border-gray-200 rounded-lg hover:bg-gray-50 disabled:opacity-40"
                        >
                          ← Anterior
                        </button>
                        <span className="text-xs text-gray-500">
                          Página {page} de {pages}
                        </span>
                        <button
                          onClick={() => loadMentions(selectedFeed.id, page + 1)}
                          disabled={page >= pages}
                          className="px-3 py-1.5 text-xs border border-gray-200 rounded-lg hover:bg-gray-50 disabled:opacity-40"
                        >
                          Siguiente →
                        </button>
                      </div>
                    )}
                  </>
                )}
              </div>
            </>
          )}
        </div>
      </div>

      {/* Modal agregar feed */}
      {showModal && (
        <AddFeedModal
          onClose={() => setShowModal(false)}
          onAdded={handleFeedAdded}
        />
      )}
    </div>
  )
}
