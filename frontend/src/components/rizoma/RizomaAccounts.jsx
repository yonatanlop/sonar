/**
 * Rizoma › Cuentas de atacantes
 * Lista de las cuentas de atacantes (de todos los casos) con filtro por tipo de red, estado y
 * búsqueda; cada cuenta abre su historial (línea de tiempo). También muestra el historial
 * reciente de todas las cuentas.
 */
import { useEffect, useState } from 'react'
import { useQuery, keepPreviousData } from '@tanstack/react-query'
import { Search, History, ExternalLink, X, ChevronLeft, ChevronRight, Ban, UserPlus, MapPin } from 'lucide-react'
import client from '../../api/client'
import CityMap from './CityMap'
import { MEDIUM_BADGE, fmtDateTime, fmtDay } from './shared'

const STATUS_LABEL = { activa: 'activas', cerrada: 'cerradas', cuenta_nueva: 'con cuenta nueva' }

const EVENT_STYLE = {
  account_created:     'bg-gray-400',
  post_added:          'bg-gray-400',
  report_added:        'bg-orange-500',
  report_removed:      'bg-gray-300',
  post_removed:        'bg-green-500',
  post_restored:       'bg-yellow-500',
  account_closed:      'bg-red-500',
  account_reopened:    'bg-yellow-500',
  new_account_created: 'bg-purple-500',
  new_account_cleared: 'bg-gray-300',
}

const fetchAccounts = (p) => client.get('/case-reports/accounts', { params: p }).then(r => r.data)
const fetchHistory  = (id) => client.get(`/case-reports/accounts/${id}/history`).then(r => r.data)
const fetchEvents   = (p) => client.get('/case-reports/events', { params: p }).then(r => r.data)

function MediumBadge({ medium }) {
  return medium
    ? <span className={`badge ${MEDIUM_BADGE[medium] || 'bg-gray-100 text-gray-600'}`}>{medium}</span>
    : <span className="text-gray-400">—</span>
}

function detailText(e) {
  const d = e.detail || {}
  if (d.post_id != null) return `Publicación #${String(d.post_id).padStart(4, '0')}`
  if (d.info) return d.info
  return ''
}

function Pager({ page, pages, total, onPage, noun }) {
  if (pages <= 1) return null
  return (
    <div className="px-4 py-3 border-t border-gray-100 flex items-center justify-between">
      <span className="text-sm text-gray-500">{total} {noun} · página {page} de {pages}</span>
      <div className="flex gap-2">
        <button className="btn-secondary px-3 py-1.5 text-sm flex items-center gap-1 disabled:opacity-40" disabled={page === 1} onClick={() => onPage(page - 1)}>
          <ChevronLeft className="w-4 h-4" /> Anterior
        </button>
        <button className="btn-secondary px-3 py-1.5 text-sm flex items-center gap-1 disabled:opacity-40" disabled={page === pages} onClick={() => onPage(page + 1)}>
          Siguiente <ChevronRight className="w-4 h-4" />
        </button>
      </div>
    </div>
  )
}

function HistoryModal({ accountId, onClose }) {
  const { data, isLoading } = useQuery({ queryKey: ['rz-history', accountId], queryFn: () => fetchHistory(accountId) })
  const a = data?.account
  return (
    <div className="fixed inset-0 z-40 bg-black/40 flex items-start justify-center p-4 overflow-y-auto" onClick={onClose}>
      <div className="bg-white rounded-xl shadow-xl w-full max-w-2xl my-8" onClick={e => e.stopPropagation()}>
        <div className="px-5 py-4 border-b border-gray-100 flex items-start justify-between gap-3">
          <div>
            <h2 className="font-semibold text-gray-900 flex items-center gap-2 flex-wrap">
              <History className="w-4 h-4 text-primary-600" /> Historial de la cuenta
            </h2>
            {a && (
              <p className="text-sm text-gray-600 mt-1 flex items-center gap-2 flex-wrap">
                <MediumBadge medium={a.medium} />
                <span className="font-medium">{a.author || 'Sin nombre'}</span>
                {a.user_id && <span className="text-xs text-gray-400">{a.user_id}</span>}
                <span className="text-xs text-gray-400">· Caso: {a.case}</span>
              </p>
            )}
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600"><X className="w-5 h-5" /></button>
        </div>

        {isLoading ? (
          <p className="text-center text-gray-400 py-10 text-sm">Cargando historial…</p>
        ) : (
          <div className="p-5 space-y-5">
            <div className="flex flex-wrap gap-2 text-xs">
              {a.account_removed
                ? <span className="badge bg-red-100 text-red-700 flex items-center gap-1"><Ban className="w-3 h-3" /> Cerrada · {fmtDay(a.removed_date)}</span>
                : <span className="badge bg-green-100 text-green-700">Activa</span>}
              {a.created_new_account && (
                <span className="badge bg-purple-100 text-purple-700 flex items-center gap-1">
                  <UserPlus className="w-3 h-3" /> Creó cuenta nueva{a.new_account_info ? `: ${a.new_account_info}` : ''}
                </span>
              )}
              {a.profile_url && (
                <a href={a.profile_url} target="_blank" rel="noopener noreferrer" className="badge bg-gray-100 text-primary-700 flex items-center gap-1">
                  Ver perfil <ExternalLink className="w-3 h-3" />
                </a>
              )}
            </div>

            <div>
              <h3 className="text-xs font-semibold tracking-wider text-primary-600 uppercase mb-3">Línea de tiempo</h3>
              {data.events.length === 0 ? (
                <p className="text-sm text-gray-400">Aún no hay eventos.</p>
              ) : (
                <ol className="relative border-l-2 border-gray-100 ml-2 space-y-4">
                  {data.events.map(e => (
                    <li key={e.id} className="pl-5 relative">
                      <span className={`absolute -left-[7px] top-1.5 w-3 h-3 rounded-full ring-2 ring-white ${EVENT_STYLE[e.type] || 'bg-gray-400'}`} />
                      <p className="text-sm font-medium text-gray-800">
                        {e.label}
                        {detailText(e) && <span className="font-normal text-gray-500"> · {detailText(e)}</span>}
                      </p>
                      <p className={`text-xs ${e.event_date ? 'text-gray-500' : 'text-amber-600'}`}>
                        {fmtDateTime(e.event_date)}
                        {e.by && <span className="text-gray-400"> · registrado por {e.by}</span>}
                      </p>
                    </li>
                  ))}
                </ol>
              )}
            </div>

            {data.posts.length > 0 && (
              <div>
                <h3 className="text-xs font-semibold tracking-wider text-primary-600 uppercase mb-2">Publicaciones ({data.posts.length})</h3>
                <div className="divide-y divide-gray-100 border border-gray-100 rounded-lg text-sm">
                  {data.posts.map(p => (
                    <div key={p.post_id} className="px-3 py-2 flex items-center gap-2 flex-wrap">
                      <span className="font-mono text-xs text-gray-400">#{String(p.post_id ?? 0).padStart(4, '0')}</span>
                      <span className="text-gray-600 flex-1 min-w-[120px] truncate">{p.affects || '—'}</span>
                      {p.reported && <span className="badge bg-orange-100 text-orange-700">Denunciada · {fmtDay(p.reported_date)}</span>}
                      {p.post_removed && <span className="badge bg-green-100 text-green-700">Eliminada · {fmtDay(p.post_removed_date)}</span>}
                      {p.publication_url && (
                        <a href={p.publication_url} target="_blank" rel="noopener noreferrer" className="text-primary-600"><ExternalLink className="w-3.5 h-3.5" /></a>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

function AccountsList({ onOpen }) {
  const [medium, setMedium] = useState('')
  const [status, setStatus] = useState('')
  const [qInput, setQInput] = useState('')
  const [q, setQ]           = useState('')
  const [page, setPage]     = useState(1)
  const [showMap, setShowMap] = useState(true)

  useEffect(() => {
    const t = setTimeout(() => { setQ(qInput.trim()); setPage(1) }, 350)
    return () => clearTimeout(t)
  }, [qInput])

  const { data, isLoading } = useQuery({
    queryKey: ['rz-accounts', medium, status, q, page],
    queryFn: () => fetchAccounts({ medium, status, q, page }),
    placeholderData: keepPreviousData,
  })
  const counts = data?.medium_counts ?? {}
  const totalAll = Object.values(counts).reduce((a, b) => a + b, 0)

  return (
    <div className="space-y-3">
      {/* Filtros */}
      <div className="card py-3 space-y-3">
        <div className="flex flex-wrap gap-2">
          {[{ value: '', label: 'Todas las redes', n: totalAll }, ...Object.keys(counts).sort().map(m => ({ value: m, label: m, n: counts[m] }))].map(o => (
            <button key={o.value} onClick={() => { setMedium(o.value); setPage(1) }}
              className={`px-3 py-1.5 rounded-lg text-sm font-medium border transition-colors ${
                medium === o.value ? 'bg-red-600 text-white border-red-600' : 'bg-white text-gray-600 border-gray-200 hover:border-gray-300'}`}>
              {o.label} <span className={medium === o.value ? 'text-red-100' : 'text-gray-400'}>({o.n})</span>
            </button>
          ))}
        </div>
        <div className="flex flex-wrap gap-2">
          <div className="relative flex-1 min-w-[220px]">
            <Search className="w-4 h-4 text-gray-400 absolute left-3 top-1/2 -translate-y-1/2" />
            <input className="input w-full pl-9" placeholder="Buscar por usuario, id, caso o ciudad…" value={qInput} onChange={e => setQInput(e.target.value)} />
          </div>
          <select className="input w-auto" value={status} onChange={e => { setStatus(e.target.value); setPage(1) }}>
            <option value="">Todos los estados</option>
            <option value="activa">Activas</option>
            <option value="cerrada">Cerradas</option>
            <option value="cuenta_nueva">Crearon cuenta nueva</option>
          </select>
        </div>
      </div>

      {/* Mapa: de dónde provienen las cuentas (respeta red, estado y búsqueda) */}
      {data && (
        <div className="space-y-2">
          <button onClick={() => setShowMap(v => !v)} className="text-sm text-primary-600 hover:underline flex items-center gap-1.5">
            <MapPin className="w-4 h-4" /> {showMap ? 'Ocultar mapa' : 'Ver mapa de origen de las cuentas'}
            <span className="text-gray-400">({data.geo_accounts} con ciudad de {data.total})</span>
          </button>
          {showMap && (
            <CityMap
              geo={data.geo}
              accounts={data.geo_accounts}
              title={`Distribución geográfica de las cuentas${medium ? ` · ${medium}` : ''}${status ? ` · ${STATUS_LABEL[status]}` : ''}`}
            />
          )}
        </div>
      )}

      <div className="card p-0 overflow-hidden">
        {isLoading ? (
          <p className="text-center text-gray-400 py-10 text-sm">Cargando cuentas…</p>
        ) : (data?.items ?? []).length === 0 ? (
          <p className="text-center text-gray-400 py-10 text-sm">No hay cuentas con estos filtros.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 border-b border-gray-100">
                <tr className="text-left text-gray-600">
                  <th className="px-4 py-2.5 font-medium">Red</th>
                  <th className="px-4 py-2.5 font-medium">Perfil</th>
                  <th className="px-4 py-2.5 font-medium">Caso</th>
                  <th className="px-4 py-2.5 font-medium">Ciudad</th>
                  <th className="px-4 py-2.5 font-medium text-center">Publicaciones</th>
                  <th className="px-4 py-2.5 font-medium">Estado</th>
                  <th className="px-4 py-2.5 font-medium">Última actividad</th>
                  <th className="px-4 py-2.5" />
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {data.items.map(a => (
                  <tr key={a.id} className="hover:bg-gray-50">
                    <td className="px-4 py-2.5"><MediumBadge medium={a.medium} /></td>
                    <td className="px-4 py-2.5 text-gray-800">
                      {a.author || '—'}
                      {a.user_id && <span className="block text-xs text-gray-400">{a.user_id}</span>}
                    </td>
                    <td className="px-4 py-2.5 text-gray-600">{a.case}</td>
                    <td className="px-4 py-2.5 text-gray-600">{a.city || '—'}</td>
                    <td className="px-4 py-2.5 text-center text-gray-700">
                      {a.posts}
                      <span className="block text-[11px] text-gray-400">{a.reported} denunc. · {a.posts_removed} elim.</span>
                    </td>
                    <td className="px-4 py-2.5">
                      <div className="flex flex-col gap-1 items-start">
                        {a.account_removed
                          ? <span className="badge bg-red-100 text-red-700">Cerrada · {fmtDay(a.removed_date)}</span>
                          : <span className="badge bg-green-100 text-green-700">Activa</span>}
                        {a.created_new_account && <span className="badge bg-purple-100 text-purple-700">Cuenta nueva</span>}
                      </div>
                    </td>
                    <td className="px-4 py-2.5 text-xs text-gray-500 whitespace-nowrap">{fmtDay(a.last_activity)}</td>
                    <td className="px-4 py-2.5">
                      <button onClick={() => onOpen(a.id)} className="text-primary-600 hover:text-primary-700 text-xs font-medium flex items-center gap-1">
                        <History className="w-3.5 h-3.5" /> Historial
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {data && <Pager page={data.page} pages={data.pages} total={data.total} onPage={setPage} noun="cuentas" />}
      </div>
    </div>
  )
}

function RecentEvents({ onOpen }) {
  const [medium, setMedium] = useState('')
  const [type, setType]     = useState('')
  const [page, setPage]     = useState(1)
  const { data, isLoading } = useQuery({
    queryKey: ['rz-events', medium, type, page],
    queryFn: () => fetchEvents({ medium, event_type: type, page }),
    placeholderData: keepPreviousData,
  })
  return (
    <div className="space-y-3">
      <div className="card py-3 flex flex-wrap gap-2">
        <select className="input w-auto" value={medium} onChange={e => { setMedium(e.target.value); setPage(1) }}>
          <option value="">Todas las redes</option>
          {['X', 'Facebook', 'Instagram', 'TikTok', 'YouTube', 'Threads', 'Sitio Web'].map(m => <option key={m}>{m}</option>)}
        </select>
        <select className="input w-auto" value={type} onChange={e => { setType(e.target.value); setPage(1) }}>
          <option value="">Todos los eventos</option>
          {Object.entries(data?.types ?? {}).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </select>
      </div>
      <div className="card p-0 overflow-hidden">
        {isLoading ? (
          <p className="text-center text-gray-400 py-10 text-sm">Cargando historial…</p>
        ) : (data?.items ?? []).length === 0 ? (
          <p className="text-center text-gray-400 py-10 text-sm">No hay eventos con estos filtros.</p>
        ) : (
          <div className="divide-y divide-gray-100">
            {data.items.map(e => (
              <button key={e.id} onClick={() => onOpen(e.account_id)} className="w-full text-left px-4 py-3 hover:bg-gray-50 flex items-center gap-3 flex-wrap">
                <span className={`w-2.5 h-2.5 rounded-full shrink-0 ${EVENT_STYLE[e.type] || 'bg-gray-400'}`} />
                <span className="text-sm font-medium text-gray-800">{e.label}</span>
                <MediumBadge medium={e.medium} />
                <span className="text-sm text-gray-600">{e.author || '—'}</span>
                <span className="text-xs text-gray-400">· {e.case}</span>
                {detailText(e) && <span className="text-xs text-gray-400">· {detailText(e)}</span>}
                <span className={`ml-auto text-xs whitespace-nowrap ${e.event_date ? 'text-gray-500' : 'text-amber-600'}`}>{fmtDateTime(e.event_date)}</span>
              </button>
            ))}
          </div>
        )}
        {data && <Pager page={data.page} pages={data.pages} total={data.total} onPage={setPage} noun="eventos" />}
      </div>
    </div>
  )
}

export default function RizomaAccounts() {
  const [view, setView] = useState('accounts')
  const [openId, setOpenId] = useState(null)
  return (
    <div className="space-y-3">
      <div className="flex gap-2">
        {[{ k: 'accounts', l: 'Cuentas' }, { k: 'events', l: 'Historial reciente' }].map(v => (
          <button key={v.k} onClick={() => setView(v.k)}
            className={`px-3 py-1.5 rounded-lg text-sm font-medium border ${view === v.k ? 'bg-gray-900 text-white border-gray-900' : 'bg-white text-gray-600 border-gray-200 hover:border-gray-300'}`}>
            {v.l}
          </button>
        ))}
      </div>
      {view === 'accounts' ? <AccountsList onOpen={setOpenId} /> : <RecentEvents onOpen={setOpenId} />}
      {openId && <HistoryModal accountId={openId} onClose={() => setOpenId(null)} />}
    </div>
  )
}
