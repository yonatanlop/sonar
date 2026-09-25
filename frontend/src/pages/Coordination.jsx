/**
 * Actividad coordinada — grupos de cuentas que publican el mismo texto (o casi) en una ventana corta.
 * El sistema propone candidatos; el equipo los confirma o descarta. Esas decisiones son la referencia
 * real para medir y calibrar el detector.
 */
import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Network, X, ExternalLink, CheckCircle, XCircle, RotateCcw, Users, Repeat, Info, AlertCircle,
} from 'lucide-react'
import toast from 'react-hot-toast'
import client from '../api/client'

const fetchSummary  = () => client.get('/coordination/summary').then(r => r.data)
const fetchClusters = (p) => client.get('/coordination/clusters', { params: p }).then(r => r.data)
const fetchCluster  = (id) => client.get(`/coordination/clusters/${id}`).then(r => r.data)
const fetchAccounts = () => client.get('/coordination/accounts', { params: { min_clusters: 2, limit: 50 } }).then(r => r.data)

const SENT = { very_negative: 'Muy negativo', negative: 'Negativo', neutral: 'Neutral', positive: 'Positivo', sin_clasificar: 'Sin clasificar' }
const SENT_COLOR = { very_negative: 'bg-red-100 text-red-700', negative: 'bg-orange-100 text-orange-700', neutral: 'bg-gray-100 text-gray-600', positive: 'bg-green-100 text-green-700', sin_clasificar: 'bg-gray-100 text-gray-400' }
const STATUS_BADGE = { nuevo: 'bg-blue-100 text-blue-700', confirmado: 'bg-red-100 text-red-700', descartado: 'bg-gray-100 text-gray-500' }

function fmtDate(dt) {
  if (!dt) return '—'
  return new Date(dt).toLocaleString('es', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' })
}
function fmtDay(dt) {
  if (!dt) return '—'
  return new Date(dt).toLocaleDateString('es', { day: '2-digit', month: 'short', year: 'numeric' })
}
function scoreBadge(s) {
  if (s >= 0.7) return 'bg-red-100 text-red-700'
  if (s >= 0.4) return 'bg-orange-100 text-orange-700'
  return 'bg-gray-100 text-gray-500'
}
function dominantSentiment(mix) {
  const e = Object.entries(mix || {}).sort((a, b) => b[1] - a[1])[0]
  return e ? e[0] : null
}
function num(n) { return n == null ? '—' : Number(n).toLocaleString('es') }

function Kpi({ label, value, sub, tip, tone = 'text-gray-900' }) {
  return (
    <div className="card text-center" title={tip}>
      <p className={`text-2xl font-bold ${tone}`}>{value}</p>
      <p className="text-xs text-gray-500 mt-0.5">{label}</p>
      {sub && <p className="text-[11px] text-gray-400 mt-0.5">{sub}</p>}
    </div>
  )
}

export default function Coordination() {
  const qc = useQueryClient()
  const [tab, setTab]         = useState('grupos')
  const [status, setStatus]   = useState('nuevo')
  const [kind, setKind]       = useState('')
  const [minScore, setMin]    = useState(0.4)
  const [openId, setOpenId]   = useState(null)

  const { data: sum } = useQuery({ queryKey: ['coord-summary'], queryFn: fetchSummary })
  const { data: clusters = [], isLoading } = useQuery({
    queryKey: ['coord-clusters', status, kind, minScore],
    queryFn: () => fetchClusters({ ...(status ? { status } : {}), ...(kind ? { kind } : {}), min_score: minScore }),
    enabled: tab === 'grupos',
  })
  const { data: accounts = [], isLoading: loadingAcc } = useQuery({
    queryKey: ['coord-accounts'], queryFn: fetchAccounts, enabled: tab === 'cuentas',
  })

  const refresh = () => {
    qc.invalidateQueries({ queryKey: ['coord-summary'] })
    qc.invalidateQueries({ queryKey: ['coord-clusters'] })
    qc.invalidateQueries({ queryKey: ['coord-accounts'] })
    if (openId) qc.invalidateQueries({ queryKey: ['coord-cluster', openId] })
  }

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between flex-wrap gap-3">
        <div className="flex items-center gap-2">
          <Network className="w-6 h-6 text-primary-600" />
          <div>
            <h1 className="text-xl font-bold text-gray-900">Actividad coordinada</h1>
            <p className="text-sm text-gray-500">Cuentas distintas publicando el mismo texto (o casi) en pocas horas</p>
          </div>
        </div>
      </div>

      <div className="card bg-blue-50 border border-blue-100 flex gap-3 text-sm text-blue-900">
        <Info className="w-5 h-5 shrink-0 mt-0.5" />
        <p>
          SONAR propone <b>candidatos</b> comparando los textos de las últimas 2 semanas de tus entidades (Twitter/X y YouTube; las
          noticias se excluyen). Un puntaje alto significa varias cuentas con pocos seguidores publicando lo mismo casi a la vez.
          <b> Revísalos y márcalos como confirmado o descartado</b>: así medimos qué tan bien acierta el detector.
        </p>
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
        <Kpi label="Por revisar" value={sum?.nuevo ?? '—'} sub={sum ? `${sum.nuevo_alto_puntaje} con puntaje ≥ 60 %` : ''} tone="text-blue-700"
             tip="Grupos detectados que nadie ha revisado todavía" />
        <Kpi label="Confirmados" value={sum?.confirmado ?? '—'} tone="text-red-600" tip="Grupos que el equipo confirmó como actividad coordinada" />
        <Kpi label="Descartados" value={sum?.descartado ?? '—'} tone="text-gray-500" tip="Grupos que el equipo descartó (falsa alarma)" />
        <Kpi label="Cuentas en redes" value={sum?.cuentas_en_redes ?? '—'} sub={sum ? `${sum.cuentas_nucleo} en 2 o más grupos` : ''}
             tip="Cuentas distintas que aparecen en grupos de red no descartados. Las que se repiten son el núcleo de la campaña" />
        <Kpi label="Acierto del detector" value={sum?.precision_revisada != null ? `${Math.round(sum.precision_revisada * 100)} %` : '—'}
             sub={sum ? `${sum.revisados} revisados` : ''}
             tip="Confirmados / (confirmados + descartados). Aparece cuando el equipo empieza a revisar" />
      </div>

      {/* Pestañas */}
      <div className="flex gap-1 border-b border-gray-200">
        {[['grupos', 'Grupos detectados'], ['cuentas', 'Cuentas núcleo']].map(([id, label]) => (
          <button key={id} onClick={() => setTab(id)}
            className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px ${tab === id ? 'border-primary-600 text-primary-700' : 'border-transparent text-gray-500 hover:text-gray-700'}`}>
            {label}
          </button>
        ))}
      </div>

      {tab === 'grupos' && (
        <>
          <div className="card py-3 flex flex-wrap gap-3 items-center">
            <select className="input w-auto" value={status} onChange={e => setStatus(e.target.value)}>
              <option value="nuevo">Por revisar</option><option value="confirmado">Confirmados</option>
              <option value="descartado">Descartados</option><option value="">Todos</option>
            </select>
            <select className="input w-auto" value={kind} onChange={e => setKind(e.target.value)}>
              <option value="">Red y repetición</option><option value="red">Varias cuentas (red)</option><option value="repeticion">Una cuenta repitiendo</option>
            </select>
            <select className="input w-auto" value={minScore} onChange={e => setMin(Number(e.target.value))}>
              <option value={0}>Cualquier puntaje</option><option value={0.4}>Puntaje ≥ 40 %</option><option value={0.6}>Puntaje ≥ 60 %</option><option value={0.8}>Puntaje ≥ 80 %</option>
            </select>
            <span className="text-xs text-gray-400">{clusters.length} grupos</span>
          </div>

          <div className="card p-0 overflow-hidden">
            {isLoading ? <div className="text-center text-gray-400 py-12">Cargando…</div>
              : clusters.length === 0 ? (
                <div className="text-center py-16 text-gray-400">
                  <AlertCircle className="w-10 h-10 mx-auto mb-3 opacity-30" />
                  <p className="font-medium">No hay grupos con estos filtros</p>
                  <p className="text-sm mt-1">El detector corre cada 3 horas.</p>
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead className="bg-gray-50 border-b border-gray-100">
                      <tr>
                        {['Puntaje', 'Entidad', 'Tipo', 'Cuentas', 'Publicaciones', 'Ventana', 'Seguidores (med.)', 'Sentimiento', 'Texto', 'Estado', ''].map(h =>
                          <th key={h} className="text-left px-4 py-3 font-medium text-gray-600 whitespace-nowrap">{h}</th>)}
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-100">
                      {clusters.map(c => {
                        const dom = dominantSentiment(c.sentiment_mix)
                        return (
                          <tr key={c.id} className="hover:bg-gray-50 cursor-pointer" onClick={() => setOpenId(c.id)}>
                            <td className="px-4 py-3"><span className={`badge font-semibold ${scoreBadge(c.score)}`}>{Math.round(c.score * 100)}</span></td>
                            <td className="px-4 py-3 text-gray-800 whitespace-nowrap">{c.entity_name}</td>
                            <td className="px-4 py-3 whitespace-nowrap">
                              {c.kind === 'red'
                                ? <span className="inline-flex items-center gap-1 text-gray-600"><Users className="w-3.5 h-3.5" /> Red</span>
                                : <span className="inline-flex items-center gap-1 text-gray-600"><Repeat className="w-3.5 h-3.5" /> Repetición</span>}
                            </td>
                            <td className="px-4 py-3 text-gray-700">{c.accounts_count}</td>
                            <td className="px-4 py-3 text-gray-700">{c.mentions_count}</td>
                            <td className="px-4 py-3 text-gray-500 text-xs whitespace-nowrap">{fmtDay(c.first_seen)}<br />{c.span_hours} h</td>
                            <td className="px-4 py-3 text-gray-600">{num(c.median_followers)}</td>
                            <td className="px-4 py-3">{dom && <span className={`badge ${SENT_COLOR[dom]}`}>{SENT[dom]}</span>}</td>
                            <td className="px-4 py-3 text-gray-600 max-w-[280px]"><span className="line-clamp-2">{c.sample_text}</span></td>
                            <td className="px-4 py-3"><span className={`badge ${STATUS_BADGE[c.status]}`}>{c.status}</span></td>
                            <td className="px-4 py-3"><span className="text-xs text-primary-700">Revisar →</span></td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                </div>
              )}
          </div>
        </>
      )}

      {tab === 'cuentas' && (
        <div className="card p-0 overflow-hidden">
          <div className="px-5 py-3 border-b border-gray-100 text-sm text-gray-500">
            Cuentas que aparecen en <b>2 o más</b> grupos de red no descartados: el núcleo de las campañas.
          </div>
          {loadingAcc ? <div className="text-center text-gray-400 py-12">Cargando…</div>
            : accounts.length === 0 ? <p className="text-center text-gray-400 py-10 text-sm">Aún no hay cuentas repetidas en varios grupos.</p>
            : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-gray-50 border-b border-gray-100">
                    <tr>{['Cuenta', 'Grupos', 'Publicaciones', 'Seguidores', 'Creada', 'Última actividad'].map(h =>
                      <th key={h} className="text-left px-4 py-3 font-medium text-gray-600">{h}</th>)}</tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {accounts.map(a => (
                      <tr key={a.author_ext_id} className="hover:bg-gray-50">
                        <td className="px-4 py-2.5">
                          <a href={`https://x.com/${a.username}`} target="_blank" rel="noopener noreferrer" className="text-primary-700 hover:underline inline-flex items-center gap-1">
                            @{a.username} <ExternalLink className="w-3 h-3" />
                          </a>
                        </td>
                        <td className="px-4 py-2.5"><span className="badge bg-red-100 text-red-700">{a.clusters}</span></td>
                        <td className="px-4 py-2.5 text-gray-700">{a.posts}</td>
                        <td className="px-4 py-2.5 text-gray-600">{num(a.followers)}</td>
                        <td className="px-4 py-2.5 text-gray-500 text-xs">{fmtDay(a.account_created)}</td>
                        <td className="px-4 py-2.5 text-gray-500 text-xs">{fmtDate(a.last_seen)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
        </div>
      )}

      {openId && <ClusterDrawer id={openId} onClose={() => setOpenId(null)} onChanged={refresh} />}
    </div>
  )
}


function ClusterDrawer({ id, onClose, onChanged }) {
  const [note, setNote] = useState('')
  const { data: c, isLoading } = useQuery({ queryKey: ['coord-cluster', id], queryFn: () => fetchCluster(id) })

  const review = useMutation({
    mutationFn: (status) => client.patch(`/coordination/clusters/${id}/review`, { status, note }),
    onSuccess: (_r, status) => {
      toast.success(status === 'confirmado' ? 'Marcado como coordinado' : status === 'descartado' ? 'Descartado' : 'Devuelto a por revisar')
      onChanged(); onClose()
    },
    onError: (e) => toast.error(e.response?.data?.detail || 'No se pudo guardar'),
  })

  return (
    <>
      <div className="fixed inset-0 bg-black/30 z-40" onClick={onClose} />
      <div className="fixed right-0 top-0 h-full w-full max-w-2xl bg-white shadow-2xl z-50 flex flex-col">
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-200">
          <h3 className="font-semibold text-gray-800">Revisar grupo</h3>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-700"><X className="w-5 h-5" /></button>
        </div>

        <div className="flex-1 overflow-y-auto p-5 space-y-5">
          {isLoading || !c ? <p className="text-center text-gray-400 py-12">Cargando…</p> : (
            <>
              <div className="grid grid-cols-3 gap-3 text-center">
                <div className="rounded-lg bg-gray-50 p-3"><p className={`text-xl font-bold ${c.score >= 0.7 ? 'text-red-600' : 'text-gray-800'}`}>{Math.round(c.score * 100)}</p><p className="text-xs text-gray-500">Puntaje</p></div>
                <div className="rounded-lg bg-gray-50 p-3"><p className="text-xl font-bold text-gray-800">{c.accounts_count}</p><p className="text-xs text-gray-500">Cuentas</p></div>
                <div className="rounded-lg bg-gray-50 p-3"><p className="text-xl font-bold text-gray-800">{c.span_hours} h</p><p className="text-xs text-gray-500">Ventana</p></div>
              </div>

              <div className="text-sm text-gray-600 space-y-1">
                <p><b>Entidad:</b> {c.entity_name} · <b>Red social:</b> {c.platform} · <b>Publicaciones:</b> {c.mentions_count}</p>
                <p><b>Seguidores (mediana):</b> {num(c.median_followers)} · <b>Cuentas con &lt; 300 seguidores:</b> {Math.round((c.low_follower_share || 0) * 100)} %</p>
                <p className="flex flex-wrap gap-1.5 items-center"><b>Sentimiento:</b>
                  {Object.entries(c.sentiment_mix || {}).map(([k, v]) => <span key={k} className={`badge ${SENT_COLOR[k]}`}>{SENT[k]} · {v}</span>)}
                </p>
              </div>

              <div>
                <h4 className="text-sm font-semibold text-gray-800 mb-2">Publicaciones ({c.members.length})</h4>
                <div className="space-y-2">
                  {c.members.map(m => (
                    <div key={m.id} className="border border-gray-100 rounded-lg p-3">
                      <div className="flex items-center justify-between gap-2 flex-wrap">
                        <a href={`https://x.com/${m.username}`} target="_blank" rel="noopener noreferrer" className="text-sm font-medium text-primary-700 hover:underline">@{m.username}</a>
                        <div className="flex items-center gap-2 text-xs text-gray-500 flex-wrap">
                          <span>{num(m.followers)} seguidores</span>
                          {m.account_created && <span>· creada {fmtDay(m.account_created)}</span>}
                          {m.network_clusters >= 2 && <span className="badge bg-red-100 text-red-700">en {m.network_clusters} grupos</span>}
                          {m.bot_probability != null && <span className="badge bg-gray-100 text-gray-600">bot {Math.round(m.bot_probability * 100)} %</span>}
                        </div>
                      </div>
                      <p className="text-sm text-gray-700 mt-1.5 whitespace-pre-line">{m.content}</p>
                      <div className="flex items-center justify-between mt-1.5 text-xs text-gray-400">
                        <span>{fmtDate(m.published_at)}</span>
                        {m.url && <a href={m.url} target="_blank" rel="noopener noreferrer" className="text-primary-600 hover:underline inline-flex items-center gap-1">Ver publicación <ExternalLink className="w-3 h-3" /></a>}
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {c.status !== 'nuevo' && (
                <p className="text-xs text-gray-500">
                  Ya revisado ({c.status}){c.reviewed_by_name ? ` por ${c.reviewed_by_name}` : ''}{c.review_note ? ` — “${c.review_note}”` : ''}.
                </p>
              )}
            </>
          )}
        </div>

        {c && (
          <div className="border-t border-gray-200 p-4 space-y-3">
            <textarea className="input w-full resize-none" rows={2} placeholder="Nota (opcional): por qué lo confirmas o descartas…"
              value={note} onChange={e => setNote(e.target.value)} />
            <div className="flex gap-2 flex-wrap">
              <button onClick={() => review.mutate('confirmado')} disabled={review.isPending}
                className="btn-primary flex-1 flex items-center justify-center gap-1.5 bg-red-600 hover:bg-red-700">
                <CheckCircle className="w-4 h-4" /> Confirmar coordinado
              </button>
              <button onClick={() => review.mutate('descartado')} disabled={review.isPending}
                className="btn-secondary flex-1 flex items-center justify-center gap-1.5">
                <XCircle className="w-4 h-4" /> Descartar
              </button>
              {c.status !== 'nuevo' && (
                <button onClick={() => review.mutate('nuevo')} disabled={review.isPending}
                  className="btn-secondary flex items-center gap-1.5" title="Volver a por revisar">
                  <RotateCcw className="w-4 h-4" />
                </button>
              )}
            </div>
          </div>
        )}
      </div>
    </>
  )
}
