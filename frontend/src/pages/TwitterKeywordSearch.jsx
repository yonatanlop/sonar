import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'react-hot-toast'
import {
  Search, Hash, Type, Plus, Trash2, Play, Square, RefreshCw,
  CheckCircle, XCircle, Clock, AlertTriangle,
} from 'lucide-react'
import client from '../api/client'

const TERM_TYPE_LABELS = { keyword: 'Keyword', hashtag: 'Hashtag' }

export default function TwitterKeywordSearch() {
  const qc = useQueryClient()

  const { data: status, isLoading: statusLoading } = useQuery({
    queryKey: ['tw-kw-status'],
    queryFn: () => client.get('/twitter-keyword-search/status').then(r => r.data),
    refetchInterval: 30_000,
  })

  const { data: terms = [], isLoading: termsLoading } = useQuery({
    queryKey: ['tw-kw-terms'],
    queryFn: () => client.get('/twitter-keyword-search/terms').then(r => r.data),
  })

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ['tw-kw-status'] })
    qc.invalidateQueries({ queryKey: ['tw-kw-terms'] })
  }

  const startMut = useMutation({
    mutationFn: () => client.post('/twitter-keyword-search/start').then(r => r.data),
    onSuccess: () => { toast.success('Búsqueda activada'); invalidate() },
    onError:   (e) => toast.error(e.response?.data?.detail ?? 'Error al activar'),
  })

  const stopMut = useMutation({
    mutationFn: () => client.post('/twitter-keyword-search/stop').then(r => r.data),
    onSuccess: () => { toast.success('Búsqueda detenida'); invalidate() },
    onError:   (e) => toast.error(e.response?.data?.detail ?? 'Error al detener'),
  })

  const triggerMut = useMutation({
    mutationFn: () => client.post('/twitter-keyword-search/trigger').then(r => r.data),
    onSuccess: () => toast.success('Búsqueda iniciada — resultados en ~1 min'),
    onError:   (e) => toast.error(e.response?.data?.detail ?? 'Error al iniciar'),
  })

  const deleteMut = useMutation({
    mutationFn: (id) => client.delete(`/twitter-keyword-search/terms/${id}`),
    onSuccess: () => { invalidate() },
    onError:   (e) => toast.error(e.response?.data?.detail ?? 'Error al eliminar'),
  })

  const toggleMut = useMutation({
    mutationFn: (id) => client.patch(`/twitter-keyword-search/terms/${id}/toggle`).then(r => r.data),
    onSuccess: () => invalidate(),
    onError:   (e) => toast.error(e.response?.data?.detail ?? 'Error al cambiar estado'),
  })

  return (
    <div className="p-6 space-y-6 max-w-3xl mx-auto">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Búsqueda Twitter Global</h1>
        <p className="text-sm text-gray-500 mt-1">
          Monitoreo continuo de keywords y hashtags. Se activa automáticamente a las <strong>8:00 PM hora Colombia</strong>.
        </p>
      </div>

      {/* ── Panel de estado ── */}
      <StatusPanel status={status} loading={statusLoading} />

      {/* ── Botones de control ── */}
      <ControlButtons
        status={status}
        startMut={startMut}
        stopMut={stopMut}
        triggerMut={triggerMut}
        onRefresh={invalidate}
      />

      {/* ── Gestión de términos ── */}
      <TermsPanel
        terms={terms}
        loading={termsLoading}
        deleteMut={deleteMut}
        toggleMut={toggleMut}
        onAdd={invalidate}
      />
    </div>
  )
}


function StatusPanel({ status, loading }) {
  if (loading) {
    return (
      <div className="card p-5 animate-pulse">
        <div className="h-5 bg-gray-200 rounded w-1/3 mb-3" />
        <div className="h-4 bg-gray-100 rounded w-1/2" />
      </div>
    )
  }

  const active = status?.is_active

  return (
    <div className="card p-5 space-y-3">
      <div className="flex items-center justify-between">
        <h2 className="font-semibold text-gray-800">Estado de la búsqueda</h2>
        <span className={`flex items-center gap-1.5 text-sm font-medium px-3 py-1 rounded-full ${
          active
            ? 'bg-green-100 text-green-700'
            : 'bg-gray-100 text-gray-500'
        }`}>
          {active
            ? <><CheckCircle className="w-3.5 h-3.5" /> Activa</>
            : <><XCircle    className="w-3.5 h-3.5" /> Inactiva</>
          }
        </span>
      </div>

      <div className="grid grid-cols-2 gap-3 text-sm text-gray-600">
        <StatItem icon={Search} label="Términos activos" value={status?.active_terms ?? 0} />
        <StatItem icon={Hash}   label="Términos totales"  value={status?.total_terms  ?? 0} />
        {status?.activated_at && (
          <StatItem icon={Play}  label="Activada"     value={fmtDate(status.activated_at)} />
        )}
        {status?.last_run_at && (
          <StatItem icon={Clock} label="Última ronda" value={fmtDate(status.last_run_at)} />
        )}
      </div>

      {!active && status?.stopped_at && (
        <p className="text-xs text-gray-400">
          Detenida: {fmtDate(status.stopped_at)}
        </p>
      )}
    </div>
  )
}


function StatItem({ icon: Icon, label, value }) {
  return (
    <div className="flex items-center gap-2">
      <Icon className="w-4 h-4 text-gray-400 shrink-0" />
      <span className="text-gray-500">{label}:</span>
      <span className="font-medium text-gray-800">{value}</span>
    </div>
  )
}


function ControlButtons({ status, startMut, stopMut, triggerMut, onRefresh }) {
  const active = status?.is_active
  const noTerms = (status?.active_terms ?? 0) === 0

  return (
    <div className="card p-5">
      <h2 className="font-semibold text-gray-800 mb-3">Control</h2>
      <div className="flex flex-wrap gap-2">

        {/* Verificar estado */}
        <button
          onClick={onRefresh}
          className="btn-secondary flex items-center gap-1.5 text-sm"
        >
          <RefreshCw className="w-4 h-4" />
          Verificar estado
        </button>

        {/* Iniciar ahora (trigger manual) */}
        <button
          onClick={() => triggerMut.mutate()}
          disabled={triggerMut.isPending || !active}
          title={!active ? 'Activa la búsqueda primero' : ''}
          className="btn-secondary flex items-center gap-1.5 text-sm disabled:opacity-40"
        >
          <Play className="w-4 h-4" />
          {triggerMut.isPending ? 'Iniciando…' : 'Iniciar ahora'}
        </button>

        {/* Activar / Detener toggle */}
        {active ? (
          <button
            onClick={() => stopMut.mutate()}
            disabled={stopMut.isPending}
            className="flex items-center gap-1.5 text-sm px-4 py-2 rounded-lg bg-red-600 text-white hover:bg-red-700 disabled:opacity-40 transition-colors font-medium"
          >
            <Square className="w-4 h-4" />
            {stopMut.isPending ? 'Deteniendo…' : 'Detener búsqueda'}
          </button>
        ) : (
          <button
            onClick={() => startMut.mutate()}
            disabled={startMut.isPending || noTerms}
            title={noTerms ? 'Agrega términos antes de activar' : ''}
            className="flex items-center gap-1.5 text-sm px-4 py-2 rounded-lg bg-green-600 text-white hover:bg-green-700 disabled:opacity-40 transition-colors font-medium"
          >
            <Play className="w-4 h-4" />
            {startMut.isPending ? 'Activando…' : 'Activar búsqueda'}
          </button>
        )}
      </div>

      {!active && noTerms && (
        <p className="mt-2 text-xs text-amber-700 flex items-center gap-1">
          <AlertTriangle className="w-3.5 h-3.5 shrink-0" />
          Agrega al menos un término para poder activar la búsqueda.
        </p>
      )}
    </div>
  )
}


const OP_COLORS = { AND: 'bg-blue-100 text-blue-700', OR: 'bg-yellow-100 text-yellow-700', NOT: 'bg-red-100 text-red-700' }

function TermLabel({ t }) {
  const primary = t.term_type === 'hashtag' ? `#${t.term}` : `"${t.term}"`

  // Construir lista de condiciones (extra_conditions tiene prioridad)
  const conditions = t.extra_conditions?.length
    ? t.extra_conditions
    : t.secondary_term ? [{ term: t.secondary_term, op: t.logic_op || 'AND' }] : []

  return (
    <span className="font-medium text-gray-800 flex items-center gap-1 flex-wrap text-sm">
      {primary}
      {conditions.map((c, i) => (
        <span key={i} className="flex items-center gap-1">
          <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${OP_COLORS[c.op] ?? OP_COLORS.AND}`}>{c.op}</span>
          &quot;{c.term}&quot;
        </span>
      ))}
    </span>
  )
}

const EMPTY_COND = () => ({ op: 'AND', term: '' })

function TermsPanel({ terms, loading, deleteMut, toggleMut, onAdd }) {
  const [newTerm, setNewTerm]   = useState('')
  const [termType, setTermType] = useState('keyword')
  const [conditions, setConds]  = useState([])   // [{op, term}]

  const addCond    = () => setConds(c => [...c, EMPTY_COND()])
  const removeCond = (i) => setConds(c => c.filter((_, j) => j !== i))
  const updateCond = (i, field, val) => setConds(c => c.map((x, j) => j === i ? { ...x, [field]: val } : x))

  const addMut = useMutation({
    mutationFn: () => client.post('/twitter-keyword-search/terms', {
      term:             newTerm.trim(),
      term_type:        termType,
      extra_conditions: termType === 'keyword' && conditions.length > 0
        ? conditions.filter(c => c.term.trim()).map(c => ({ term: c.term.trim(), op: c.op }))
        : null,
    }).then(r => r.data),
    onSuccess: () => {
      toast.success('Término agregado')
      setNewTerm('')
      setConds([])
      onAdd()
    },
    onError: (e) => toast.error(e.response?.data?.detail ?? 'Error al agregar'),
  })

  const handleAdd = (e) => {
    e.preventDefault()
    if (!newTerm.trim()) return
    addMut.mutate()
  }

  return (
    <div className="card p-5 space-y-4">
      <h2 className="font-semibold text-gray-800">Términos de búsqueda</h2>

      {/* Formulario agregar */}
      <form onSubmit={handleAdd} className="space-y-2">
        {/* Fila principal */}
        <div className="flex gap-2">
          <select
            value={termType}
            onChange={(e) => { setTermType(e.target.value); setConds([]) }}
            className="input w-32 text-sm"
          >
            <option value="keyword">Keyword</option>
            <option value="hashtag">Hashtag</option>
          </select>
          <input
            value={newTerm}
            onChange={(e) => setNewTerm(e.target.value)}
            placeholder={termType === 'hashtag' ? 'colombia (sin #)' : 'término principal'}
            className="input flex-1 text-sm"
          />
          <button
            type="submit"
            disabled={addMut.isPending || !newTerm.trim()}
            className="btn-primary flex items-center gap-1.5 text-sm disabled:opacity-40 shrink-0"
          >
            <Plus className="w-4 h-4" />
            {addMut.isPending ? 'Agregando…' : 'Agregar'}
          </button>
        </div>

        {/* Condiciones adicionales (solo keywords) */}
        {termType === 'keyword' && (
          <div className="pl-2 space-y-1.5">
            {conditions.map((cond, i) => (
              <div key={i} className="flex gap-2 items-center">
                <select
                  value={cond.op}
                  onChange={(e) => updateCond(i, 'op', e.target.value)}
                  className="input w-28 text-sm"
                >
                  <option value="AND">AND — y</option>
                  <option value="OR">OR  — o</option>
                  <option value="NOT">NOT — excluir</option>
                </select>
                <input
                  value={cond.term}
                  onChange={(e) => updateCond(i, 'term', e.target.value)}
                  placeholder="término adicional"
                  className="input flex-1 text-sm"
                />
                <button type="button" onClick={() => removeCond(i)}
                  className="p-1.5 text-gray-400 hover:text-red-500 transition-colors">
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            ))}
            <button type="button" onClick={addCond}
              className="flex items-center gap-1 text-xs text-blue-600 hover:text-blue-800 mt-1">
              <Plus className="w-3.5 h-3.5" /> Agregar condición
            </button>
          </div>
        )}
      </form>

      {/* Ejemplos */}
      {termType === 'keyword' && (
        <div className="text-xs text-gray-400 bg-gray-50 rounded-lg px-3 py-2 space-y-0.5">
          <p><span className="font-medium text-gray-600">AND:</span> tweets que contengan todos los términos</p>
          <p><span className="font-medium text-gray-600">OR:</span>  tweets que contengan cualquiera de los términos</p>
          <p><span className="font-medium text-gray-600">NOT:</span> excluye tweets que contengan ese término</p>
          <p className="pt-1 text-gray-500">Ej: "MIRA" AND "coalición" NOT "uribismo" → tweets de MIRA sobre coalición sin mencionar uribismo</p>
        </div>
      )}


      {/* Lista de términos */}
      {loading ? (
        <div className="space-y-2">
          {[1,2,3].map(i => (
            <div key={i} className="h-10 bg-gray-100 rounded-lg animate-pulse" />
          ))}
        </div>
      ) : terms.length === 0 ? (
        <div className="text-center py-8 text-gray-400">
          <Search className="w-8 h-8 mx-auto mb-2 opacity-40" />
          <p className="text-sm">No hay términos configurados</p>
        </div>
      ) : (
        <ul className="space-y-1.5">
          {terms.map(t => (
            <li key={t.id} className={`flex items-center gap-3 px-3 py-2.5 rounded-lg border ${
              t.is_active ? 'border-gray-200 bg-white' : 'border-dashed border-gray-200 bg-gray-50 opacity-60'
            }`}>
              {t.term_type === 'hashtag'
                ? <Hash  className="w-4 h-4 text-blue-500 shrink-0" />
                : <Type  className="w-4 h-4 text-purple-500 shrink-0" />
              }
              <div className="flex-1 text-sm min-w-0">
                <TermLabel t={t} />
              </div>
              <span className={`badge text-xs shrink-0 ${
                t.term_type === 'hashtag' ? 'bg-blue-50 text-blue-700' : 'bg-purple-50 text-purple-700'
              }`}>
                {TERM_TYPE_LABELS[t.term_type]}
              </span>
              <button
                onClick={() => toggleMut.mutate(t.id)}
                disabled={toggleMut.isPending}
                title={t.is_active ? 'Desactivar' : 'Activar'}
                className={`text-xs px-2 py-0.5 rounded font-medium transition-colors ${
                  t.is_active
                    ? 'bg-green-100 text-green-700 hover:bg-green-200'
                    : 'bg-gray-100 text-gray-500 hover:bg-gray-200'
                }`}
              >
                {t.is_active ? 'Activo' : 'Inactivo'}
              </button>
              <button
                onClick={() => deleteMut.mutate(t.id)}
                disabled={deleteMut.isPending}
                className="p-1 text-gray-400 hover:text-red-500 transition-colors"
                title="Eliminar"
              >
                <Trash2 className="w-4 h-4" />
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}


function fmtDate(isoStr) {
  if (!isoStr) return '—'
  return new Date(isoStr).toLocaleString('es-CO', {
    dateStyle: 'short',
    timeStyle: 'short',
    timeZone: 'America/Bogota',
  })
}
