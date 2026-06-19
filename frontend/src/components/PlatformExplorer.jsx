/**
 * PlatformExplorer — componente genérico para los Explorers de redes sociales.
 * Replica el patrón de Twitter Explorer (panel izquierdo de monitores + panel
 * derecho de publicaciones con filtros y paginación), parametrizado por red.
 *
 * Props de configuración:
 *   apiBase     — prefijo del endpoint (ej: '/facebook-feeds')
 *   title       — título de la página
 *   subtitle    — descripción corta
 *   HeaderIcon  — componente de icono lucide para la cabecera
 *   itemNoun    — sustantivo de las publicaciones ('publicaciones', 'videos')
 *   feedTypes   — [{ value, icon, label, placeholder, groupLabel }]
 *   theme       — objeto con clases Tailwind explícitas (ver páginas concretas)
 */
import { useState, useEffect, useCallback } from 'react'
import {
  Plus, Trash2, ChevronRight, RefreshCw, Calendar, Filter,
  ExternalLink, Search, ShieldAlert, ImageOff,
} from 'lucide-react'
import api from '../api/client'

// ── Card de publicación ───────────────────────────────────────

function PostCard({ mention, theme }) {
  const [imgErr, setImgErr] = useState(false)
  const date = mention.published_at
    ? new Date(mention.published_at).toLocaleString('es-CO', {
        day: '2-digit', month: 'short', year: 'numeric',
        hour: '2-digit', minute: '2-digit',
      })
    : '—'

  let thumb = null
  try {
    const arr = mention.media_urls ? JSON.parse(mention.media_urls) : null
    thumb = Array.isArray(arr) && arr.length ? arr[0] : null
  } catch { /* media_urls no es JSON */ }

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-4 hover:shadow-md transition-shadow">
      <div className="flex items-start justify-between gap-2 mb-2">
        <span className="font-medium text-sm text-gray-800 truncate">
          {mention.author_username ? `@${mention.author_username}` : 'Desconocido'}
        </span>
        {mention.url && (
          <a href={mention.url} target="_blank" rel="noopener noreferrer"
             className={`text-gray-400 ${theme.linkHover} transition-colors shrink-0`} title="Ver original">
            <ExternalLink className="w-3.5 h-3.5" />
          </a>
        )}
      </div>

      <div className="flex gap-3">
        {thumb && !imgErr && (
          <img src={thumb} alt="" onError={() => setImgErr(true)}
               className="w-16 h-16 rounded-lg object-cover shrink-0 bg-gray-100" />
        )}
        <p className="text-sm text-gray-700 leading-relaxed line-clamp-4 flex-1">{mention.content}</p>
      </div>

      <div className="flex items-center justify-between mt-3 text-xs text-gray-400">
        <span className="flex items-center gap-1"><Calendar className="w-3 h-3" /> {date}</span>
        <div className="flex items-center gap-3">
          {mention.reach > 0 && <span>❤️ {mention.reach.toLocaleString()}</span>}
          {mention.language && <span className="uppercase font-mono">{mention.language}</span>}
        </div>
      </div>
    </div>
  )
}

// ── Item de monitor (panel izquierdo) ─────────────────────────

function FeedItem({ feed, selected, onClick, onDelete, onToggleRizoma, theme, typeIcons, itemNoun }) {
  const Icon = typeIcons[feed.feed_type] || Search
  return (
    <div
      className={`flex items-center gap-2 px-3 py-2.5 rounded-lg cursor-pointer group transition-colors ${
        selected ? theme.selectedBg + ' border' : 'hover:bg-gray-50 border border-transparent'
      } ${feed.is_rizoma ? 'border-l-2 border-l-red-400' : ''}`}
      onClick={onClick}
    >
      <div className={`rounded-full p-1 ${selected ? theme.selectedIconBg : 'bg-gray-100'}`}>
        <Icon className={`w-3 h-3 ${selected ? theme.selectedIconText : 'text-gray-500'}`} />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-gray-800 truncate">{feed.display_name}</p>
        <div className="flex items-center gap-1.5">
          <p className="text-xs text-gray-400">{feed.mention_count} {itemNoun}</p>
          {feed.is_rizoma && (
            <span className="text-[10px] bg-red-100 text-red-600 px-1.5 rounded-full font-medium">Rizoma</span>
          )}
        </div>
      </div>
      <button
        onClick={(e) => { e.stopPropagation(); onToggleRizoma(feed.id) }}
        className={`opacity-0 group-hover:opacity-100 transition-all ${feed.is_rizoma ? 'text-red-500 opacity-100' : 'text-gray-300 hover:text-red-400'}`}
        title={feed.is_rizoma ? 'Quitar de Rizoma' : 'Marcar como Rizoma'}
      >
        <ShieldAlert className="w-3.5 h-3.5" />
      </button>
      <button
        onClick={(e) => { e.stopPropagation(); onDelete(feed.id) }}
        className="opacity-0 group-hover:opacity-100 text-gray-300 hover:text-red-500 transition-all"
        title="Eliminar monitor"
      >
        <Trash2 className="w-3.5 h-3.5" />
      </button>
      {selected && <ChevronRight className={`w-3.5 h-3.5 ${theme.chevron} shrink-0`} />}
    </div>
  )
}

// ── Modal de alta ─────────────────────────────────────────────

function AddFeedModal({ apiBase, feedTypes, theme, onClose, onAdded }) {
  const [feedType, setFeedType] = useState(feedTypes[0].value)
  const [term, setTerm]         = useState('')
  const [loading, setLoading]   = useState(false)
  const [error, setError]       = useState('')

  const current = feedTypes.find((t) => t.value === feedType) || feedTypes[0]

  async function handleSubmit(e) {
    e.preventDefault()
    if (!term.trim()) return
    setLoading(true)
    setError('')
    try {
      const { data } = await api.post(apiBase, { feed_type: feedType, term: term.trim() })
      onAdded(data)
      onClose()
    } catch (err) {
      setError(err.response?.data?.detail || 'Error al agregar el monitor')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4" onClick={onClose}>
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-md p-6" onClick={(e) => e.stopPropagation()}>
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Agregar monitor</h3>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5">Tipo</label>
            <div className="flex gap-2">
              {feedTypes.map(({ value, icon: Icon, label }) => (
                <button
                  key={value}
                  type="button"
                  onClick={() => setFeedType(value)}
                  className={`flex-1 flex flex-col items-center gap-1 py-2.5 rounded-lg border text-xs font-medium transition-colors ${
                    feedType === value ? theme.modalTypeActive : 'border-gray-200 text-gray-500 hover:bg-gray-50'
                  }`}
                >
                  <Icon className="w-4 h-4" />
                  {label}
                </button>
              ))}
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5">{current.label}</label>
            <input
              type="text"
              value={term}
              onChange={(e) => setTerm(e.target.value)}
              placeholder={current.placeholder}
              className={`w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 ${theme.ring}`}
              autoFocus
            />
          </div>

          {error && <p className="text-sm text-red-600">{error}</p>}

          <div className="flex gap-2 pt-1">
            <button type="button" onClick={onClose}
              className="flex-1 px-4 py-2 border border-gray-300 rounded-lg text-sm text-gray-600 hover:bg-gray-50">
              Cancelar
            </button>
            <button type="submit" disabled={loading || !term.trim()}
              className={`flex-1 px-4 py-2 text-white rounded-lg text-sm font-medium disabled:opacity-50 ${theme.modalBtn}`}>
              {loading ? 'Agregando...' : 'Agregar'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

// ── Página principal ──────────────────────────────────────────

export default function PlatformExplorer({
  apiBase, title, subtitle, HeaderIcon, itemNoun = 'publicaciones', feedTypes, theme,
}) {
  const [feeds, setFeeds]               = useState([])
  const [selectedFeed, setSelectedFeed] = useState(null)
  const [mentions, setMentions]         = useState([])
  const [total, setTotal]               = useState(0)
  const [page, setPage]                 = useState(1)
  const [pages, setPages]               = useState(1)
  const [loadingFeeds, setLoadingFeeds] = useState(true)
  const [loadingMentions, setLoadingMentions] = useState(false)
  const [showModal, setShowModal]       = useState(false)

  const [dateFrom, setDateFrom]   = useState('')
  const [dateTo, setDateTo]       = useState('')
  const [feedFilter, setFeedFilter] = useState('')
  const [searchQ, setSearchQ]     = useState('')

  const typeIcons = Object.fromEntries(feedTypes.map((t) => [t.value, t.icon]))

  const loadFeeds = useCallback(async () => {
    setLoadingFeeds(true)
    try {
      const { data } = await api.get(apiBase)
      setFeeds(data)
    } finally {
      setLoadingFeeds(false)
    }
  }, [apiBase])

  useEffect(() => { loadFeeds() }, [loadFeeds])

  const loadMentions = useCallback(async (feedId, pg = 1) => {
    if (!feedId) return
    setLoadingMentions(true)
    try {
      const params = { page: pg }
      if (dateFrom) params.date_from = dateFrom
      if (dateTo)   params.date_to   = dateTo
      if (searchQ.trim().length >= 2) params.q = searchQ.trim()
      const { data } = await api.get(`${apiBase}/${feedId}/mentions`, { params })
      setMentions(data.mentions)
      setTotal(data.total)
      setPage(data.page)
      setPages(data.pages)
    } finally {
      setLoadingMentions(false)
    }
  }, [apiBase, dateFrom, dateTo, searchQ])

  useEffect(() => {
    if (selectedFeed) loadMentions(selectedFeed.id, 1)
  }, [selectedFeed, dateFrom, dateTo, searchQ, loadMentions])

  function handleSelectFeed(feed) { setSelectedFeed(feed); setPage(1); setMentions([]) }

  async function handleDeleteFeed(feedId) {
    if (!confirm('¿Eliminar este monitor? No se borrarán las publicaciones ya recolectadas.')) return
    await api.delete(`${apiBase}/${feedId}`)
    setFeeds((prev) => prev.filter((f) => f.id !== feedId))
    if (selectedFeed?.id === feedId) { setSelectedFeed(null); setMentions([]) }
  }

  async function handleToggleRizoma(feedId) {
    const { data } = await api.patch(`${apiBase}/${feedId}/rizoma`)
    setFeeds((prev) => prev.map((f) => f.id === feedId ? data : f))
  }

  function handleFeedAdded(feed) { setFeeds((prev) => [...prev, feed]); setSelectedFeed(feed) }
  function resetFilters() { setDateFrom(''); setDateTo(''); setSearchQ('') }

  const _match = (f) => !feedFilter || f.display_name.toLowerCase().includes(feedFilter.toLowerCase())
  const groups = feedTypes.map((t) => ({
    label: t.groupLabel,
    items: feeds.filter((f) => f.feed_type === t.value && _match(f)),
  })).filter((g) => g.items.length > 0)

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <div className={`rounded-lg p-2 ${theme.iconBg}`}>
            <HeaderIcon className={`w-5 h-5 ${theme.iconText}`} />
          </div>
          <div>
            <h1 className="text-xl font-bold text-gray-900">{title}</h1>
            <p className="text-xs text-gray-500">{subtitle}</p>
          </div>
        </div>
        <button
          onClick={() => setShowModal(true)}
          className={`flex items-center gap-1.5 text-white px-3 py-2 rounded-lg text-sm font-medium transition-colors ${theme.addBtn}`}
        >
          <Plus className="w-4 h-4" /> Agregar monitor
        </button>
      </div>

      {/* Cuerpo */}
      <div className="flex-1 flex flex-col md:flex-row gap-4 min-h-0">
        {/* Panel izquierdo */}
        <div className="w-full md:w-64 shrink-0 max-h-52 md:max-h-none bg-white rounded-xl border border-gray-200 flex flex-col overflow-hidden">
          <div className="px-3 py-2.5 border-b border-gray-100 flex items-center justify-between">
            <span className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Monitores</span>
            <button onClick={loadFeeds} className="text-gray-400 hover:text-gray-600" title="Actualizar lista">
              <RefreshCw className="w-3.5 h-3.5" />
            </button>
          </div>

          {!loadingFeeds && feeds.length > 0 && (
            <div className="px-2 pt-2 relative">
              <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-gray-400 pointer-events-none" />
              <input
                value={feedFilter}
                onChange={(e) => setFeedFilter(e.target.value)}
                placeholder="Buscar monitor..."
                className={`w-full text-xs border border-gray-200 rounded-lg py-1.5 pl-7 pr-2 focus:outline-none focus:ring-1 ${theme.ring}`}
              />
            </div>
          )}

          <div className="flex-1 overflow-y-auto p-2 space-y-3">
            {loadingFeeds ? (
              <p className="text-xs text-gray-400 text-center pt-4">Cargando...</p>
            ) : feeds.length === 0 ? (
              <div className="text-center pt-6 px-3">
                <HeaderIcon className="w-8 h-8 text-gray-200 mx-auto mb-2" />
                <p className="text-xs text-gray-400">Sin monitores aún.</p>
                <button onClick={() => setShowModal(true)} className={`mt-2 text-xs ${theme.iconText} hover:underline`}>
                  + Agregar primero
                </button>
              </div>
            ) : groups.length === 0 ? (
              <p className="text-xs text-gray-400 text-center pt-4">Sin resultados</p>
            ) : (
              groups.map((g) => (
                <div key={g.label}>
                  <p className="text-xs text-gray-400 px-3 mb-1 font-medium">{g.label}</p>
                  {g.items.map((f) => (
                    <FeedItem
                      key={f.id}
                      feed={f}
                      selected={selectedFeed?.id === f.id}
                      onClick={() => handleSelectFeed(f)}
                      onDelete={handleDeleteFeed}
                      onToggleRizoma={handleToggleRizoma}
                      theme={theme}
                      typeIcons={typeIcons}
                      itemNoun={itemNoun}
                    />
                  ))}
                </div>
              ))
            )}
          </div>
        </div>

        {/* Panel derecho */}
        <div className="flex-1 flex flex-col min-w-0">
          {!selectedFeed ? (
            <div className="flex-1 flex items-center justify-center bg-white rounded-xl border border-gray-200">
              <div className="text-center">
                <HeaderIcon className="w-12 h-12 text-gray-200 mx-auto mb-3" />
                <p className="text-gray-400 text-sm">Selecciona un monitor para ver sus {itemNoun}</p>
              </div>
            </div>
          ) : (
            <>
              <div className="bg-white rounded-xl border border-gray-200 px-4 py-3 mb-3 flex flex-wrap items-center gap-3">
                <div className="flex items-center gap-1.5 text-sm font-semibold text-gray-700">
                  <HeaderIcon className={`w-4 h-4 ${theme.iconText}`} />
                  {selectedFeed.display_name}
                  <span className="text-xs text-gray-400 font-normal">({total} {itemNoun})</span>
                </div>
                <div className="ml-auto flex flex-wrap items-center gap-2">
                  <Filter className="w-3.5 h-3.5 text-gray-400" />
                  <div className="relative">
                    <Search className="absolute left-2 top-1/2 -translate-y-1/2 w-3 h-3 text-gray-400 pointer-events-none" />
                    <input
                      type="text"
                      value={searchQ}
                      onChange={(e) => setSearchQ(e.target.value)}
                      placeholder="Buscar..."
                      className={`text-xs border border-gray-200 rounded-lg pl-6 pr-2 py-1.5 w-40 focus:outline-none focus:ring-1 ${theme.ring}`}
                    />
                  </div>
                  <input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)}
                    className={`text-xs border border-gray-200 rounded-lg px-2 py-1.5 focus:outline-none focus:ring-1 ${theme.ring}`} />
                  <input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)}
                    className={`text-xs border border-gray-200 rounded-lg px-2 py-1.5 focus:outline-none focus:ring-1 ${theme.ring}`} />
                  {(dateFrom || dateTo || searchQ) && (
                    <button onClick={resetFilters} className={`text-xs ${theme.iconText} hover:underline`}>Limpiar</button>
                  )}
                  <button onClick={() => loadMentions(selectedFeed.id, page)}
                    className={`text-gray-400 ${theme.linkHover} transition-colors`} title="Actualizar">
                    <RefreshCw className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>

              <div className="flex-1 overflow-y-auto space-y-3">
                {loadingMentions ? (
                  <div className="flex items-center justify-center pt-12">
                    <RefreshCw className={`w-5 h-5 ${theme.spinner} animate-spin`} />
                  </div>
                ) : mentions.length === 0 ? (
                  <div className="flex flex-col items-center justify-center pt-12 text-center">
                    <ImageOff className="w-10 h-10 text-gray-200 mb-3" />
                    <p className="text-gray-400 text-sm">Sin {itemNoun} aún.</p>
                    <p className="text-gray-400 text-xs mt-1">El scraper recolecta datos periódicamente.</p>
                  </div>
                ) : (
                  <>
                    {mentions.map((m) => <PostCard key={m.id} mention={m} theme={theme} />)}
                    {pages > 1 && (
                      <div className="flex items-center justify-center gap-2 pt-2 pb-4">
                        <button onClick={() => loadMentions(selectedFeed.id, page - 1)} disabled={page <= 1}
                          className="px-3 py-1.5 text-xs border border-gray-200 rounded-lg hover:bg-gray-50 disabled:opacity-40">
                          ← Anterior
                        </button>
                        <span className="text-xs text-gray-500">Página {page} de {pages}</span>
                        <button onClick={() => loadMentions(selectedFeed.id, page + 1)} disabled={page >= pages}
                          className="px-3 py-1.5 text-xs border border-gray-200 rounded-lg hover:bg-gray-50 disabled:opacity-40">
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

      {showModal && (
        <AddFeedModal apiBase={apiBase} feedTypes={feedTypes} theme={theme}
          onClose={() => setShowModal(false)} onAdded={handleFeedAdded} />
      )}
    </div>
  )
}
