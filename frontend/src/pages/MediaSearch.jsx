/**
 * Módulo 8 — Búsqueda Inversa de Imágenes y Videos
 * Encuentra dónde fue publicada una imagen o video y quién la publicó.
 */
import { useState, useRef, useCallback, useEffect } from 'react'
import { useSearchParams } from 'react-router-dom'
import {
  ScanSearch, Upload, Link2, X, ExternalLink, ImageOff,
  ChevronDown, ChevronRight, AlertCircle, Loader2, CheckCircle2,
  Twitter, Youtube, Instagram, Globe, Clock, Sparkles, AlertTriangle,
} from 'lucide-react'
import { useMutation } from '@tanstack/react-query'
import { toast } from 'react-hot-toast'
import api from '../api/client'

// ── Constantes ────────────────────────────────────────────────

const ENGINES = [
  {
    id: 'internal',
    label: 'SONAR',
    description: 'Busca entre todo lo recopilado por SONAR',
    alwaysOn: true,
  },
  {
    id: 'google_vision',
    label: 'Google Vision',
    description: 'Google Cloud Vision Web Detection',
    alwaysOn: false,
  },
  {
    id: 'saucenao',
    label: 'SauceNAO',
    description: 'Búsqueda inversa gratuita — 200/día',
    alwaysOn: false,
  },
  {
    id: 'yandex',
    label: 'Yandex',
    description: 'Yandex Reverse Image — requiere SerpApi key',
    alwaysOn: false,
  },
  {
    id: 'tineye',
    label: 'TinEye',
    description: 'Especializado en copias exactas (plan de pago)',
    alwaysOn: false,
  },
]

const PLATFORM_ICONS = {
  twitter:   <Twitter  className="w-3.5 h-3.5 text-sky-500"   />,
  instagram: <Instagram className="w-3.5 h-3.5 text-pink-500" />,
  youtube:   <Youtube  className="w-3.5 h-3.5 text-red-500"   />,
}

const ENGINE_LABELS = {
  sonar_internal: 'SONAR (interno)',
  google_vision:  'Google Vision',
  saucenao:       'SauceNAO',
  yandex:         'Yandex',
  tineye:         'TinEye',
}

const ALL_ENGINE_KEYS = ['internal', 'google_vision', 'saucenao', 'yandex', 'tineye']

// ── Helpers ───────────────────────────────────────────────────

function formatDate(iso) {
  if (!iso) return null
  return new Date(iso).toLocaleString('es-CO', {
    day: '2-digit', month: 'short', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  })
}

function PlatformIcon({ platform }) {
  return PLATFORM_ICONS[platform] || <Globe className="w-3.5 h-3.5 text-gray-400" />
}

// ── Componentes ───────────────────────────────────────────────

function ResultCard({ item }) {
  const [imgErr, setImgErr] = useState(false)

  return (
    <div className="flex gap-3 p-3 rounded-lg border border-gray-100 hover:bg-gray-50 transition-colors">
      {/* Thumbnail */}
      <div className="w-16 h-16 rounded-lg overflow-hidden bg-gray-100 shrink-0 flex items-center justify-center">
        {item.thumbnail && !imgErr ? (
          <img
            src={item.thumbnail}
            alt=""
            className="w-full h-full object-cover"
            onError={() => setImgErr(true)}
          />
        ) : (
          <ImageOff className="w-5 h-5 text-gray-300" />
        )}
      </div>

      {/* Info */}
      <div className="flex-1 min-w-0">
        {/* Fuente + plataforma */}
        <div className="flex items-center gap-1.5 mb-1 flex-wrap">
          {item.platform && <PlatformIcon platform={item.platform} />}
          <span className="text-xs font-semibold text-gray-500 truncate">
            {item.source || item.platform || 'Fuente desconocida'}
          </span>
          {item.type === 'full_match' && (
            <span className="text-[10px] bg-green-100 text-green-700 px-1.5 rounded-full font-medium">
              coincidencia exacta
            </span>
          )}
          {item.similarity !== undefined && (
            <span className="text-[10px] bg-primary-100 text-primary-700 px-1.5 rounded-full font-medium">
              {Math.round(item.similarity * 100)}% similar
            </span>
          )}
        </div>

        {/* Título o autor */}
        {(item.title || item.name) && (
          <p className="text-xs text-gray-700 truncate mb-0.5">{item.title || item.name}</p>
        )}
        {item.author && (
          <p className="text-xs text-gray-500">@{item.author}</p>
        )}

        {/* Fecha */}
        {(item.published_at || item.first_seen) && (
          <div className="flex items-center gap-1 mt-1">
            <Clock className="w-3 h-3 text-gray-400" />
            <span className="text-[10px] text-gray-400">
              {formatDate(item.published_at || item.first_seen)}
            </span>
          </div>
        )}
      </div>

      {/* Link externo */}
      {item.url && (
        <a
          href={item.url}
          target="_blank"
          rel="noopener noreferrer"
          className="shrink-0 p-1.5 rounded-lg hover:bg-gray-200 text-gray-400 hover:text-primary-600 transition-colors"
          title="Abrir enlace"
        >
          <ExternalLink className="w-4 h-4" />
        </a>
      )}
    </div>
  )
}

function EngineResultGroup({ engineKey, items, skipped }) {
  const [open, setOpen] = useState(true)
  const label = ENGINE_LABELS[engineKey] || engineKey
  const isSkipped = skipped?.includes(engineKey)

  return (
    <div className="card p-0 overflow-hidden">
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center justify-between px-4 py-3 hover:bg-gray-50"
      >
        <div className="flex items-center gap-2">
          {open ? <ChevronDown className="w-4 h-4 text-gray-400" /> : <ChevronRight className="w-4 h-4 text-gray-400" />}
          <span className="font-medium text-sm text-gray-700">{label}</span>
          {isSkipped ? (
            <span className="text-[10px] bg-gray-100 text-gray-500 px-2 py-0.5 rounded-full">
              No configurado
            </span>
          ) : (
            <span className="text-[10px] bg-primary-100 text-primary-700 px-2 py-0.5 rounded-full font-medium">
              {items.length} resultado{items.length !== 1 ? 's' : ''}
            </span>
          )}
        </div>
      </button>

      {open && (
        <div className="px-4 pb-4 space-y-2">
          {isSkipped ? (
            <p className="text-xs text-gray-400 italic py-2">
              API key no configurada — actívala en el archivo .env del servidor.
            </p>
          ) : items.length === 0 ? (
            <p className="text-xs text-gray-400 italic py-2">Sin resultados para este motor.</p>
          ) : (
            items.map((item, i) => <ResultCard key={i} item={item} />)
          )}
        </div>
      )}
    </div>
  )
}

// ── Página principal ──────────────────────────────────────────

export default function MediaSearch() {
  const [searchParams] = useSearchParams()

  // Entrada
  const [mode, setMode]         = useState('upload')   // 'upload' | 'url'
  const [url, setUrl]           = useState('')
  const [file, setFile]         = useState(null)
  const [preview, setPreview]   = useState(null)
  const [isDragging, setIsDrag] = useState(false)
  const fileRef = useRef()

  // Motores seleccionados
  const [engines, setEngines] = useState(new Set(['internal']))

  // Resultados
  const [result, setResult]   = useState(null)
  const [aiResult, setAiResult] = useState(null)

  const toggleEngine = (id) => {
    if (id === 'internal') return
    setEngines(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  // ── Mutations ────────────────────────────────────────────────

  const searchByUrl = useMutation({
    mutationFn: (data) => api.post('/media-search/by-url', data).then(r => r.data),
    onSuccess: (data) => {
      setResult(data)
      if (data.total_results === 0) toast('Sin resultados encontrados')
    },
    onError: (e) => {
      const detail = e?.response?.data?.detail
      toast.error(typeof detail === 'string' ? detail : 'Error al buscar')
    },
  })

  const searchByUpload = useMutation({
    mutationFn: (formData) => api.post('/media-search/by-upload', formData, {
      headers: { 'Content-Type': undefined },
    }).then(r => r.data),
    onSuccess: (data) => {
      setResult(data)
      if (data.total_results === 0) toast('Sin resultados encontrados')
    },
    onError: (e) => {
      const detail = e?.response?.data?.detail
      const msg = Array.isArray(detail) ? detail.map(d => d.msg).join(', ') : (detail || 'Error al buscar')
      toast.error(msg)
    },
  })

  const searchFromMention = useMutation({
    mutationFn: (id) => api.get(`/media-search/from-mention/${id}?engines=${[...engines].join(',')}`).then(r => r.data),
    onSuccess: (data) => {
      setResult(data)
      if (data.total_results === 0) toast('Sin resultados encontrados')
    },
    onError: (e) => toast.error(e?.response?.data?.detail || 'Error al buscar'),
  })

  const detectAI = useMutation({
    mutationFn: (formData) => api.post('/media-search/ai-detect', formData, {
      headers: { 'Content-Type': undefined },
    }).then(r => r.data),
    onSuccess: setAiResult,
    onError: (e) => {
      const detail = e?.response?.data?.detail
      toast.error(typeof detail === 'string' ? detail : 'Error al analizar la imagen')
    },
  })

  // Si viene de una mención (?from_mention=<id>), buscar automáticamente
  useEffect(() => {
    const mentionId = searchParams.get('from_mention')
    if (mentionId) searchFromMention.mutate(mentionId)
  }, [])  // eslint-disable-line react-hooks/exhaustive-deps

  const isSearching = searchByUrl.isPending || searchByUpload.isPending || searchFromMention.isPending
  const hasInput = mode === 'url' ? url.trim() : !!file

  const handleFile = useCallback((f) => {
    if (!f) return
    setFile(f)
    setAiResult(null)
    if (f.type.startsWith('image/')) {
      setPreview(URL.createObjectURL(f))
    } else {
      setPreview(null)
    }
  }, [])

  const handleDrop = useCallback((e) => {
    e.preventDefault()
    setIsDrag(false)
    const f = e.dataTransfer.files?.[0]
    if (f) { setMode('upload'); handleFile(f) }
  }, [handleFile])

  const handleSearch = () => {
    setResult(null)
    setAiResult(null)
    const engList = [...engines]
    if (mode === 'url') {
      if (!url.trim()) { toast.error('Ingresa una URL'); return }
      searchByUrl.mutate({ url: url.trim(), engines: engList })
    } else {
      if (!file) { toast.error('Selecciona un archivo'); return }
      const fd = new FormData()
      fd.append('file', file)
      fd.append('engines', engList.join(','))
      searchByUpload.mutate(fd)
    }
  }

  const handleDetectAI = () => {
    setAiResult(null)
    const fd = new FormData()
    if (mode === 'url') {
      if (!url.trim()) { toast.error('Ingresa una URL'); return }
      fd.append('url', url.trim())
    } else {
      if (!file) { toast.error('Selecciona un archivo'); return }
      fd.append('file', file)
    }
    detectAI.mutate(fd)
  }

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="bg-primary-100 rounded-xl p-2.5">
          <ScanSearch className="w-6 h-6 text-primary-600" />
        </div>
        <div>
          <h1 className="text-xl font-bold text-gray-900">Búsqueda por Imagen</h1>
          <p className="text-sm text-gray-500">Encuentra dónde fue publicada una imagen o video, quién la publicó y si fue generada por IA</p>
        </div>
      </div>

      {/* Input */}
      <div className="card space-y-4">
        {/* Tabs modo */}
        <div className="flex gap-2">
          <button
            onClick={() => setMode('upload')}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
              mode === 'upload' ? 'bg-primary-600 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            }`}
          >
            <Upload className="w-4 h-4" /> Subir archivo
          </button>
          <button
            onClick={() => setMode('url')}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
              mode === 'url' ? 'bg-primary-600 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            }`}
          >
            <Link2 className="w-4 h-4" /> Pegar URL
          </button>
        </div>

        {/* Zona de entrada */}
        {mode === 'upload' ? (
          <div
            onDragOver={(e) => { e.preventDefault(); setIsDrag(true) }}
            onDragLeave={() => setIsDrag(false)}
            onDrop={handleDrop}
            onClick={() => fileRef.current?.click()}
            className={`relative border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-colors ${
              isDragging ? 'border-primary-400 bg-primary-50' : 'border-gray-200 hover:border-primary-300 hover:bg-gray-50'
            }`}
          >
            <input
              ref={fileRef}
              type="file"
              className="hidden"
              accept="image/jpeg,image/png,image/webp,image/gif,video/mp4,video/quicktime,video/webm"
              onChange={(e) => handleFile(e.target.files?.[0])}
            />
            {file ? (
              <div className="flex flex-col items-center gap-3">
                {preview ? (
                  <img src={preview} alt="preview" className="h-32 rounded-lg object-contain" />
                ) : (
                  <div className="w-16 h-16 bg-gray-100 rounded-lg flex items-center justify-center">
                    <Upload className="w-6 h-6 text-gray-400" />
                  </div>
                )}
                <div className="flex items-center gap-2">
                  <span className="text-sm text-gray-600">{file.name}</span>
                  <button
                    onClick={(e) => { e.stopPropagation(); setFile(null); setPreview(null); setAiResult(null) }}
                    className="text-gray-400 hover:text-red-500"
                  >
                    <X className="w-4 h-4" />
                  </button>
                </div>
              </div>
            ) : (
              <div className="flex flex-col items-center gap-2 text-gray-400">
                <Upload className="w-8 h-8" />
                <span className="text-sm">Arrastra una imagen o video aquí, o haz clic para seleccionar</span>
                <span className="text-xs">JPG, PNG, WEBP, GIF, MP4, MOV — máx 50 MB</span>
              </div>
            )}
          </div>
        ) : (
          <input
            type="url"
            className="input w-full"
            placeholder="https://pbs.twimg.com/media/... o cualquier URL de imagen/video"
            value={url}
            onChange={(e) => { setUrl(e.target.value); setAiResult(null) }}
            onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
          />
        )}

        {/* Selector de motores */}
        <div>
          <p className="text-xs font-semibold text-gray-500 mb-2 uppercase tracking-wide">Buscar en</p>
          <div className="flex flex-wrap gap-2">
            {ENGINES.map(eng => {
              const active = engines.has(eng.id)
              return (
                <button
                  key={eng.id}
                  onClick={() => toggleEngine(eng.id)}
                  disabled={eng.alwaysOn}
                  title={eng.description}
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium border transition-colors ${
                    active
                      ? 'bg-primary-600 text-white border-primary-600'
                      : 'bg-white text-gray-600 border-gray-200 hover:border-primary-300'
                  } ${eng.alwaysOn ? 'opacity-80 cursor-default' : ''}`}
                >
                  {active && <CheckCircle2 className="w-3 h-3" />}
                  {eng.label}
                </button>
              )
            })}
          </div>
        </div>

        {/* Botones de acción */}
        <div className="flex gap-3">
          <button
            onClick={handleSearch}
            disabled={isSearching || !hasInput}
            className="btn-primary flex-1 flex items-center justify-center gap-2"
          >
            {isSearching ? (
              <><Loader2 className="w-4 h-4 animate-spin" /> Buscando...</>
            ) : (
              <><ScanSearch className="w-4 h-4" /> Buscar</>
            )}
          </button>

          <button
            onClick={handleDetectAI}
            disabled={detectAI.isPending || !hasInput}
            title="Detectar si la imagen fue generada por IA (HuggingFace, gratis)"
            className="btn-secondary flex items-center justify-center gap-2 px-4"
          >
            {detectAI.isPending ? (
              <><Loader2 className="w-4 h-4 animate-spin" /> Analizando...</>
            ) : (
              <><Sparkles className="w-4 h-4" /> ¿Es IA?</>
            )}
          </button>
        </div>

        {/* Resultado detección IA */}
        {aiResult && (
          <div className={`flex items-center gap-3 p-4 rounded-xl border-l-4 ${
            aiResult.is_ai
              ? 'border-amber-400 bg-amber-50'
              : 'border-green-400 bg-green-50'
          }`}>
            {aiResult.is_ai
              ? <AlertTriangle className="w-5 h-5 text-amber-500 shrink-0" />
              : <CheckCircle2  className="w-5 h-5 text-green-500  shrink-0" />
            }
            <div>
              <p className="font-semibold text-sm text-gray-800">{aiResult.label}</p>
              <p className="text-xs text-gray-500">{Math.round(aiResult.confidence * 100)}% de confianza</p>
            </div>
          </div>
        )}
      </div>

      {/* Resultados de búsqueda */}
      {result && (
        <div className="space-y-4">
          {/* Resumen */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              {result.total_results > 0 ? (
                <CheckCircle2 className="w-5 h-5 text-green-500" />
              ) : (
                <AlertCircle className="w-5 h-5 text-gray-400" />
              )}
              <span className="font-semibold text-gray-700">
                {result.total_results > 0
                  ? `${result.total_results} publicación${result.total_results !== 1 ? 'es' : ''} encontrada${result.total_results !== 1 ? 's' : ''}`
                  : 'No se encontraron publicaciones'}
              </span>
            </div>
            {result.query_phash && (
              <span className="text-xs text-gray-400 font-mono">pHash: {result.query_phash.slice(0, 8)}…</span>
            )}
          </div>

          {/* Grupos por motor */}
          {ALL_ENGINE_KEYS.map(key => {
            const items   = result.results?.[key] || []
            const skipped = result.engines_skipped || []
            if (!result.engines_used?.includes(key) && !skipped.includes(key)) return null
            return (
              <EngineResultGroup
                key={key}
                engineKey={key}
                items={items}
                skipped={skipped}
              />
            )
          })}
        </div>
      )}
    </div>
  )
}
