/**
 * Reporte de Seguimiento a caso.
 * - Distribución geográfica de las cuentas por ciudad de origen (mapa de Colombia
 *   con burbujas + ranking).
 * - Cuentas y publicaciones cerradas en el mes seleccionado.
 * - Descarga del reporte en PDF.
 */
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { FileBarChart, Ban, Download, ExternalLink, AlertCircle } from 'lucide-react'
import toast from 'react-hot-toast'
import client from '../api/client'
import CityMap from '../components/rizoma/CityMap'

function fmtDate(dt) {
  if (!dt) return '—'
  return new Date(dt).toLocaleDateString('es', { day: '2-digit', month: 'short', year: 'numeric' })
}
function currentMonth() {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`
}

const fetchSummary = (month) => client.get('/case-reports/summary', { params: { month } }).then(r => r.data)

export default function CaseReports() {
  const [month, setMonth] = useState(currentMonth())
  const [downloading, setDownloading] = useState(false)

  const { data, isLoading } = useQuery({ queryKey: ['case-report', month], queryFn: () => fetchSummary(month) })

  const geo = data?.geo || []

  async function downloadPdf() {
    setDownloading(true)
    try {
      const res = await client.get('/case-reports/pdf', { params: { month }, responseType: 'blob' })
      const url = URL.createObjectURL(res.data)
      const a = document.createElement('a')
      a.href = url; a.download = `reporte_seguimiento_${month}.pdf`
      document.body.appendChild(a); a.click(); a.remove()
      URL.revokeObjectURL(url)
    } catch { toast.error('No se pudo generar el PDF') }
    finally { setDownloading(false) }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-2">
          <FileBarChart className="w-6 h-6 text-primary-600" />
          <div>
            <h1 className="text-xl font-bold text-gray-900">Reporte de Seguimiento</h1>
            <p className="text-sm text-gray-500">Distribución geográfica y cierres del mes</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <input type="month" className="input w-auto" value={month} onChange={e => setMonth(e.target.value)} />
          <button onClick={downloadPdf} disabled={downloading} className="btn-primary flex items-center gap-1.5">
            <Download className="w-4 h-4" /> {downloading ? 'Generando…' : 'Descargar PDF'}
          </button>
        </div>
      </div>

      {isLoading ? (
        <div className="text-center text-gray-400 py-12">Cargando reporte…</div>
      ) : (
        <>
          {/* KPIs */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            <div className="card text-center"><p className="text-2xl font-bold text-gray-900">{data.totals.accounts}</p><p className="text-xs text-gray-500 mt-0.5">Cuentas monitoreadas</p></div>
            <div className="card text-center"><p className="text-2xl font-bold text-gray-900">{data.totals.cities}</p><p className="text-xs text-gray-500 mt-0.5">Ciudades de origen</p></div>
            <div className="card text-center"><p className="text-2xl font-bold text-red-600">{data.totals.accounts_closed}</p><p className="text-xs text-gray-500 mt-0.5">Cuentas cerradas · {data.month_label}</p></div>
            <div className="card text-center"><p className="text-2xl font-bold text-orange-600">{data.totals.posts_closed}</p><p className="text-xs text-gray-500 mt-0.5">Publicaciones cerradas · {data.month_label}</p></div>
          </div>

          <CityMap geo={geo} accounts={data.totals.accounts_with_city} />

          {/* Cuentas cerradas */}
          <div className="card p-0 overflow-hidden">
            <div className="px-5 py-3 border-b border-gray-100 flex items-center gap-2">
              <Ban className="w-4 h-4 text-red-500" />
              <h2 className="font-semibold text-gray-800">Cuentas cerradas en {data.month_label}</h2>
              <span className="badge bg-red-50 text-red-600">{data.accounts_closed.length}</span>
            </div>
            {data.accounts_closed.length === 0 ? (
              <p className="text-center text-gray-400 py-8 text-sm">No se cerraron cuentas en este mes.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-gray-50 border-b border-gray-100">
                    <tr>
                      <th className="text-left px-5 py-2.5 font-medium text-gray-600">Caso</th>
                      <th className="text-left px-5 py-2.5 font-medium text-gray-600">Red</th>
                      <th className="text-left px-5 py-2.5 font-medium text-gray-600">Perfil</th>
                      <th className="text-left px-5 py-2.5 font-medium text-gray-600">Ciudad</th>
                      <th className="text-left px-5 py-2.5 font-medium text-gray-600">Cerrada</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {data.accounts_closed.map((a, i) => (
                      <tr key={i} className="hover:bg-gray-50">
                        <td className="px-5 py-2.5 text-gray-800">{a.case}</td>
                        <td className="px-5 py-2.5">{a.medium ? <span className="badge bg-primary-50 text-primary-700">{a.medium}</span> : '—'}</td>
                        <td className="px-5 py-2.5 text-gray-700">{a.author || '—'}{a.user_id && <span className="block text-xs text-gray-400">{a.user_id}</span>}</td>
                        <td className="px-5 py-2.5 text-gray-600">{a.city || '—'}</td>
                        <td className="px-5 py-2.5 text-gray-500 text-xs whitespace-nowrap">{fmtDate(a.removed_date)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* Publicaciones cerradas */}
          <div className="card p-0 overflow-hidden">
            <div className="px-5 py-3 border-b border-gray-100 flex items-center gap-2">
              <AlertCircle className="w-4 h-4 text-orange-500" />
              <h2 className="font-semibold text-gray-800">Publicaciones cerradas en {data.month_label}</h2>
              <span className="badge bg-orange-50 text-orange-600">{data.posts_closed.length}</span>
            </div>
            {data.posts_closed.length === 0 ? (
              <p className="text-center text-gray-400 py-8 text-sm">No se cerraron publicaciones en este mes.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm whitespace-nowrap">
                  <thead className="bg-gray-50 border-b border-gray-100">
                    <tr>
                      <th className="text-left px-5 py-2.5 font-medium text-gray-600">#</th>
                      <th className="text-left px-5 py-2.5 font-medium text-gray-600">Caso</th>
                      <th className="text-left px-5 py-2.5 font-medium text-gray-600">Red</th>
                      <th className="text-left px-5 py-2.5 font-medium text-gray-600">Perfil</th>
                      <th className="text-left px-5 py-2.5 font-medium text-gray-600">Afecta a</th>
                      <th className="text-left px-5 py-2.5 font-medium text-gray-600">Cerrada</th>
                      <th className="px-5 py-2.5" />
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {data.posts_closed.map((p, i) => (
                      <tr key={i} className="hover:bg-gray-50">
                        <td className="px-5 py-2.5 text-gray-400 font-mono text-xs">{p.post_id != null ? String(p.post_id).padStart(4, '0') : '—'}</td>
                        <td className="px-5 py-2.5 text-gray-800">{p.case}</td>
                        <td className="px-5 py-2.5">{p.medium ? <span className="badge bg-primary-50 text-primary-700">{p.medium}</span> : '—'}</td>
                        <td className="px-5 py-2.5 text-gray-700">{p.author || '—'}</td>
                        <td className="px-5 py-2.5 text-gray-600 max-w-[180px] truncate">{p.affects || '—'}</td>
                        <td className="px-5 py-2.5 text-gray-500 text-xs">{fmtDate(p.removed_date)}</td>
                        <td className="px-5 py-2.5">
                          {p.publication_url && <a href={p.publication_url} target="_blank" rel="noopener noreferrer" className="text-primary-600 hover:text-primary-700"><ExternalLink className="w-3.5 h-3.5" /></a>}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  )
}
