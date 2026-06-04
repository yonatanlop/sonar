/**
 * Generador de Keywords por Tema (IA)
 * Genera expresiones booleanas (AND/OR/NOT) a partir de un tema y las guarda
 * en una entidad o en el buscador global de Twitter; o lanza búsqueda en vivo.
 */
import { useState } from 'react'
import {
  Wand2, Sparkles, Loader2, Save, Radio, Building2, Globe,
  CheckCircle2, AlertCircle, X,
} from 'lucide-react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { toast } from 'react-hot-toast'
import client from '../api/client'

// ── Helpers ───────────────────────────────────────────────────

const OP_LABEL = { AND: 'Y', OR: 'O', NOT: 'SIN' }
const OP_CLASS = {
  AND: 'bg-blue-100 text-blue-700',
  OR:  'bg-green-100 text-green-700',
  NOT: 'bg-red-100 text-red-700',
}

/** Renderiza una expresión como chips de términos + operadores colorizados. */
function ExpressionChips({ terms, ops }) {
  if (!terms || terms.length === 0) return null
  const nodes = []
  terms.forEach((t, i) => {
    if (i > 0) {
      const op = (ops?.[i - 1] || 'AND').toUpperCase()
      nodes.push(
        <span key={`op-${i}`} className={`px-1.5 rounded text-xs font-bold ${OP_CLASS[op] || OP_CLASS.AND}`}>
          {OP_LABEL[op] || op}
        </span>
      )
    }
    nodes.push(
      <span key={`t-${i}`} className="text-sm text-gray-800 font-medium">"{t}"</span>
    )
  })
  return <span className="flex flex-wrap gap-1 items-center font-mono">{nodes}</span>
}

// ── Página ────────────────────────────────────────────────────

export default function TopicKeywords() {
  const [topic, setTopic]   = useState('')
  const [intent, setIntent] = useState('')

  // Resultados generados + selección
  const [results, setResults]   = useState([])      // [{expression, terms, ops, rationale}]
  const [selected, setSelected] = useState(new Set())

  // Destino
  const [target, setTarget]       = useState('entity')   // 'entity' | 'global'
  const [entityId, setEntityId]   = useState('')

  // Entidades para el dropdown
  const { data: entities = [] } = useQuery({
    queryKey: ['entities-for-topic-kw'],
    queryFn: () => client.get('/entities', { params: { active_only: false } }).then(r => r.data),
  })

  // ── Mutations ────────────────────────────────────────────────

  const generate = useMutation({
    mutationFn: () => client.post('/topic-keywords/generate', {
      topic: topic.trim(),
      intent: intent.trim(),
      max_keywords: 8,
    }).then(r => r.data),
    onSuccess: (data) => {
      const kws = data.keywords || []
      setResults(kws)
      setSelected(new Set(kws.map((_, i) => i)))   // todas seleccionadas
      if (kws.length === 0) toast('La IA no generó keywords, reformula el tema')
    },
    onError: (e) => {
      const detail = e?.response?.data?.detail
      toast.error(typeof detail === 'string' ? detail : 'Error al generar keywords')
    },
  })

  const save = useMutation({
    mutationFn: () => {
      const keywords = results
        .filter((_, i) => selected.has(i))
        .map(r => ({ expression: r.expression, terms: r.terms, ops: r.ops, language: 'es', weight: 1 }))
      const url = target === 'entity'
        ? `/topic-keywords/save-to-entity/${entityId}`
        : '/topic-keywords/save-global'
      return client.post(url, { keywords }).then(r => r.data)
    },
    onSuccess: (data) => {
      if (target === 'entity') {
        toast.success(`${data.saved} keyword(s) guardada(s) en la entidad`)
      } else {
        const extra = data.skipped ? ` · ${data.skipped} ya existían` : ''
        toast.success(`${data.saved} keyword(s) global(es) guardada(s)${extra}`)
      }
    },
    onError: (e) => {
      const detail = e?.response?.data?.detail
      toast.error(typeof detail === 'string' ? detail : 'Error al guardar')
    },
  })

  const liveSearch = useMutation({
    mutationFn: () => client.post('/topic-keywords/live-search').then(r => r.data),
    onSuccess: (data) => toast.success(data.message || 'Búsqueda iniciada'),
    onError: (e) => {
      const detail = e?.response?.data?.detail
      toast.error(typeof detail === 'string' ? detail : 'Error al iniciar búsqueda')
    },
  })

  // ── Handlers ─────────────────────────────────────────────────

  const handleGenerate = () => {
    if (!topic.trim()) { toast.error('Ingresa un tema'); return }
    setResults([]); setSelected(new Set())
    generate.mutate()
  }

  const toggleSelect = (i) => {
    setSelected(prev => {
      const next = new Set(prev)
      if (next.has(i)) next.delete(i)
      else next.add(i)
      return next
    })
  }

  const removeResult = (i) => {
    setResults(prev => prev.filter((_, idx) => idx !== i))
    setSelected(prev => {
      const next = new Set()
      ;[...prev].forEach(idx => {
        if (idx < i) next.add(idx)
        else if (idx > i) next.add(idx - 1)
      })
      return next
    })
  }

  const handleSave = () => {
    if (selected.size === 0) { toast.error('Selecciona al menos una keyword'); return }
    if (target === 'entity' && !entityId) { toast.error('Selecciona una entidad'); return }
    save.mutate()
  }

  const selectedCount = selected.size

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="bg-primary-100 rounded-xl p-2.5">
          <Wand2 className="w-6 h-6 text-primary-600" />
        </div>
        <div>
          <h1 className="text-xl font-bold text-gray-900">Generar Keywords con IA</h1>
          <p className="text-sm text-gray-500">
            Describe un tema y la IA genera expresiones de búsqueda con operadores lógicos
          </p>
        </div>
      </div>

      {/* Entrada del tema */}
      <div className="card space-y-4">
        <div>
          <label className="label">Tema u objetivo</label>
          <input
            type="text"
            className="input w-full"
            placeholder="Ej: Piraquive, @cuenta, #ReformaPensional, corrupción partido..."
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleGenerate()}
          />
        </div>
        <div>
          <label className="label">¿Qué necesitas encontrar? <span className="text-gray-400 font-normal">(opcional)</span></label>
          <textarea
            className="input w-full resize-none"
            rows={2}
            placeholder="Ej: críticas o escándalos relacionados, excluir noticias deportivas..."
            value={intent}
            onChange={(e) => setIntent(e.target.value)}
          />
        </div>
        <button
          onClick={handleGenerate}
          disabled={generate.isPending || !topic.trim()}
          className="btn-primary w-full flex items-center justify-center gap-2"
        >
          {generate.isPending
            ? <><Loader2 className="w-4 h-4 animate-spin" /> Generando...</>
            : <><Sparkles className="w-4 h-4" /> Generar keywords con IA</>
          }
        </button>
      </div>

      {/* Resultados generados */}
      {results.length > 0 && (
        <div className="space-y-4">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="w-5 h-5 text-green-500" />
            <span className="font-semibold text-gray-700">
              {results.length} expresion{results.length !== 1 ? 'es' : ''} generada{results.length !== 1 ? 's' : ''}
              <span className="text-gray-400 font-normal"> · {selectedCount} seleccionada{selectedCount !== 1 ? 's' : ''}</span>
            </span>
          </div>

          <div className="space-y-2">
            {results.map((r, i) => (
              <div
                key={i}
                className={`card flex items-start gap-3 transition-colors ${
                  selected.has(i) ? 'border-primary-200 bg-primary-50/30' : 'opacity-60'
                }`}
              >
                <input
                  type="checkbox"
                  checked={selected.has(i)}
                  onChange={() => toggleSelect(i)}
                  className="mt-1 w-4 h-4 accent-primary-600 cursor-pointer"
                />
                <div className="flex-1 min-w-0">
                  <ExpressionChips terms={r.terms} ops={r.ops} />
                  {r.rationale && (
                    <p className="text-xs text-gray-500 mt-1.5">{r.rationale}</p>
                  )}
                </div>
                <button
                  onClick={() => removeResult(i)}
                  className="text-gray-300 hover:text-red-500 shrink-0"
                  title="Descartar"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>
            ))}
          </div>

          {/* Destino */}
          <div className="card space-y-4">
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Destino</p>
            <div className="flex gap-2">
              <button
                onClick={() => setTarget('entity')}
                className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium border transition-colors ${
                  target === 'entity' ? 'bg-primary-600 text-white border-primary-600' : 'bg-white text-gray-600 border-gray-200 hover:border-primary-300'
                }`}
              >
                <Building2 className="w-4 h-4" /> Una entidad
              </button>
              <button
                onClick={() => setTarget('global')}
                className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium border transition-colors ${
                  target === 'global' ? 'bg-primary-600 text-white border-primary-600' : 'bg-white text-gray-600 border-gray-200 hover:border-primary-300'
                }`}
              >
                <Globe className="w-4 h-4" /> Búsqueda global
              </button>
            </div>

            {target === 'entity' ? (
              <div>
                <label className="label">Entidad destino</label>
                <select className="input w-full" value={entityId} onChange={(e) => setEntityId(e.target.value)}>
                  <option value="">Selecciona una entidad...</option>
                  {entities.map(e => (
                    <option key={e.id} value={e.id}>{e.name}</option>
                  ))}
                </select>
                <p className="text-xs text-gray-400 mt-1">
                  Las keywords alimentarán todos los scrapers de esta entidad (Twitter, Facebook, Instagram, YouTube, Reddit).
                </p>
              </div>
            ) : (
              <p className="text-xs text-gray-500">
                Se guardarán como términos del buscador global de Twitter/X. Luego puedes lanzar una búsqueda en vivo.
              </p>
            )}

            {/* Acciones */}
            <div className="flex gap-3 pt-1">
              <button
                onClick={handleSave}
                disabled={save.isPending || selectedCount === 0}
                className="btn-primary flex-1 flex items-center justify-center gap-2"
              >
                {save.isPending
                  ? <><Loader2 className="w-4 h-4 animate-spin" /> Guardando...</>
                  : <><Save className="w-4 h-4" /> Guardar keywords</>
                }
              </button>

              {target === 'global' && (
                <button
                  onClick={() => liveSearch.mutate()}
                  disabled={liveSearch.isPending}
                  title="Solo Twitter/X · resultados en ~1 min"
                  className="btn-secondary flex items-center justify-center gap-2 px-4"
                >
                  {liveSearch.isPending
                    ? <><Loader2 className="w-4 h-4 animate-spin" /> Iniciando...</>
                    : <><Radio className="w-4 h-4" /> Búsqueda en vivo</>
                  }
                </button>
              )}
            </div>
            {target === 'global' && (
              <p className="text-[11px] text-gray-400 flex items-center gap-1">
                <AlertCircle className="w-3 h-3" /> La búsqueda en vivo cubre solo Twitter/X (única plataforma on-demand).
              </p>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
