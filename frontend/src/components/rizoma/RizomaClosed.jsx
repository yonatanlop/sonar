/**
 * Rizoma › Cerradas
 * Cuentas, publicaciones y grupos cerrados en un rango de fechas (hora de Colombia),
 * filtrables por tipo de red.
 */
import { useState } from 'react'
import { useQuery, keepPreviousData } from '@tanstack/react-query'
import { Ban, AlertCircle, UsersRound, ExternalLink } from 'lucide-react'
import client from '../../api/client'
import { MEDIUMS, MEDIUM_BADGE, fmtDay, fmtIsoDay } from './shared'

const fetchClosed = (p) => client.get('/case-reports/closed', { params: p }).then(r => r.data)

function MediumBadge({ medium }) {
  return medium
    ? <span className={`badge ${MEDIUM_BADGE[medium] || 'bg-gray-100 text-gray-600'}`}>{medium}</span>
    : '—'
}

function Section({ icon: Icon, color, title, count, empty, children }) {
  return (
    <div className="card p-0 overflow-hidden">
      <div className="px-5 py-3 border-b border-gray-100 flex items-center gap-2">
        <Icon className={`w-4 h-4 ${color}`} />
        <h2 className="font-semibold text-gray-800">{title}</h2>
        <span className="badge bg-gray-100 text-gray-600">{count}</span>
      </div>
      {count === 0 ? <p className="text-center text-gray-400 py-8 text-sm">{empty}</p> : <div className="overflow-x-auto">{children}</div>}
    </div>
  )
}

const TH = 'text-left px-5 py-2.5 font-medium text-gray-600'

export default function RizomaClosed() {
  const [medium, setMedium]     = useState('')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo]     = useState('')

  const { data, isLoading, error } = useQuery({
    queryKey: ['rz-closed', medium, dateFrom, dateTo],
    queryFn: () => fetchClosed({ medium, date_from: dateFrom, date_to: dateTo }),
    placeholderData: keepPreviousData,
  })

  return (
    <div className="space-y-4">
      <div className="card py-3 space-y-2">
        <div className="flex flex-wrap items-center gap-3">
          <select className="input w-auto" value={medium} onChange={e => setMedium(e.target.value)}>
            <option value="">Todas las redes</option>
            {MEDIUMS.map(m => <option key={m}>{m}</option>)}
          </select>
          <div className="flex items-center gap-2 text-sm text-gray-500">
            Desde <input type="date" className="input w-auto" value={dateFrom} onChange={e => setDateFrom(e.target.value)} />
            hasta <input type="date" className="input w-auto" value={dateTo} onChange={e => setDateTo(e.target.value)} />
            {(dateFrom || dateTo) && (
              <button className="text-xs text-primary-600 hover:underline" onClick={() => { setDateFrom(''); setDateTo('') }}>Restablecer</button>
            )}
          </div>
        </div>
        {data && (
          <p className="text-xs text-gray-400">
            Período: <span className="font-medium text-gray-500">{fmtIsoDay(data.date_from)} – {fmtIsoDay(data.date_to)}</span> (hora de Colombia; por defecto, los últimos 30 días).
            {(data.undated.accounts > 0 || data.undated.posts > 0) && (
              <span className="text-amber-600"> Sin fecha registrada: {data.undated.accounts} cuentas y {data.undated.posts} publicaciones cerradas (no entran en ningún período).</span>
            )}
          </p>
        )}
      </div>

      {error ? (
        <div className="card text-center text-red-600 py-8 text-sm">No se pudo cargar. Revisa las fechas e inténtalo de nuevo.</div>
      ) : isLoading ? (
        <div className="text-center text-gray-400 py-12">Cargando…</div>
      ) : data && (
        <>
          <Section icon={Ban} color="text-red-500" title="Cuentas cerradas" count={data.totals.accounts} empty="No se cerraron cuentas en este período.">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 border-b border-gray-100">
                <tr><th className={TH}>Caso</th><th className={TH}>Red</th><th className={TH}>Perfil</th><th className={TH}>Ciudad</th><th className={TH}>Cerrada</th><th className={TH}>Cuenta nueva</th></tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {data.accounts.map(a => (
                  <tr key={a.account_id} className="hover:bg-gray-50">
                    <td className="px-5 py-2.5 text-gray-800">{a.case}</td>
                    <td className="px-5 py-2.5"><MediumBadge medium={a.medium} /></td>
                    <td className="px-5 py-2.5 text-gray-700">{a.author || '—'}{a.user_id && <span className="block text-xs text-gray-400">{a.user_id}</span>}</td>
                    <td className="px-5 py-2.5 text-gray-600">{a.city || '—'}</td>
                    <td className="px-5 py-2.5 text-gray-500 text-xs whitespace-nowrap">{fmtDay(a.removed_date)}</td>
                    <td className="px-5 py-2.5">{a.created_new_account ? <span className="badge bg-purple-100 text-purple-700">Sí</span> : <span className="text-gray-400">—</span>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Section>

          <Section icon={AlertCircle} color="text-orange-500" title="Publicaciones cerradas" count={data.totals.posts} empty="No se eliminaron publicaciones en este período.">
            <table className="w-full text-sm whitespace-nowrap">
              <thead className="bg-gray-50 border-b border-gray-100">
                <tr><th className={TH}>#</th><th className={TH}>Caso</th><th className={TH}>Red</th><th className={TH}>Perfil</th><th className={TH}>Afecta a</th><th className={TH}>Denunciada</th><th className={TH}>Eliminada</th><th className="px-5 py-2.5" /></tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {data.posts.map(p => (
                  <tr key={`${p.account_id}-${p.post_id}`} className="hover:bg-gray-50">
                    <td className="px-5 py-2.5 text-gray-400 font-mono text-xs">{p.post_id != null ? String(p.post_id).padStart(4, '0') : '—'}</td>
                    <td className="px-5 py-2.5 text-gray-800">{p.case}</td>
                    <td className="px-5 py-2.5"><MediumBadge medium={p.medium} /></td>
                    <td className="px-5 py-2.5 text-gray-700">{p.author || '—'}</td>
                    <td className="px-5 py-2.5 text-gray-600 max-w-[180px] truncate">{p.affects || '—'}</td>
                    <td className="px-5 py-2.5 text-gray-500 text-xs">{fmtDay(p.reported_date)}</td>
                    <td className="px-5 py-2.5 text-gray-500 text-xs">{fmtDay(p.removed_date)}</td>
                    <td className="px-5 py-2.5">
                      {p.publication_url && <a href={p.publication_url} target="_blank" rel="noopener noreferrer" className="text-primary-600 hover:text-primary-700"><ExternalLink className="w-3.5 h-3.5" /></a>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Section>

          {(!medium || medium === 'Facebook') && (
            <Section icon={UsersRound} color="text-indigo-500" title="Grupos de Facebook cerrados" count={data.totals.groups} empty="No se cerraron grupos en este período.">
              <table className="w-full text-sm">
                <thead className="bg-gray-50 border-b border-gray-100">
                  <tr><th className={TH}>Grupo</th><th className={TH}>Razón</th><th className={TH}>Inicio</th><th className={TH}>Cierre</th></tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {data.groups.map(g => (
                    <tr key={g.id} className="hover:bg-gray-50">
                      <td className="px-5 py-2.5"><a href={g.group_url} target="_blank" rel="noopener noreferrer" className="text-primary-600 hover:underline break-all">{g.group_url}</a></td>
                      <td className="px-5 py-2.5 text-gray-600">{g.reason || '—'}</td>
                      <td className="px-5 py-2.5 text-gray-500 text-xs whitespace-nowrap">{fmtDay(g.start_date)}</td>
                      <td className="px-5 py-2.5 text-gray-500 text-xs whitespace-nowrap">{fmtDay(g.end_date)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </Section>
          )}
        </>
      )}
    </div>
  )
}
