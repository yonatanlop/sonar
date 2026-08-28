/**
 * Reporte de Seguimiento a caso.
 * - Distribución geográfica de las cuentas por ciudad de origen (mapa de Colombia
 *   con burbujas + ranking).
 * - Cuentas y publicaciones cerradas en el mes seleccionado.
 * - Descarga del reporte en PDF.
 */
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { FileBarChart, MapPin, Ban, Download, ExternalLink, AlertCircle } from 'lucide-react'
import toast from 'react-hot-toast'
import client from '../api/client'

// Contorno de Colombia (GeoJSON público proyectado a este viewBox)
const GEO = { lonMin: -78.9909, lonMax: -66.8763, latMax: 12.4373, W: 520, H: 718.3 }
const SX = GEO.W / (GEO.lonMax - GEO.lonMin)
const proj = (lon, lat) => [(lon - GEO.lonMin) * SX, (GEO.latMax - lat) * SX]
const COL_PATH = "M155.3 540.4 L136.9 530.2 L115.8 516.0 L103.6 522.8 L67.2 516.9 L56.8 498.4 L48.8 499.1 L5.8 474.6 L0.0 461.3 L16.0 458.0 L14.1 436.5 L24.2 421.0 L45.5 418.1 L63.5 391.1 L80.0 368.6 L64.2 358.4 L72.3 333.5 L62.6 294.2 L71.8 282.9 L65.0 246.6 L47.6 223.8 L53.1 202.9 L67.0 206.0 L75.0 193.2 L65.1 168.0 L70.3 161.7 L92.5 163.0 L124.7 133.1 L142.3 128.5 L142.8 114.3 L150.7 78.0 L175.3 58.1 L202.3 57.3 L205.8 48.4 L239.3 51.9 L273.1 30.3 L289.9 20.7 L310.6 0.0 L325.8 2.6 L337.1 13.9 L328.8 28.4 L301.2 35.6 L290.3 57.0 L273.7 69.3 L261.2 85.3 L256.0 115.9 L244.1 141.0 L266.2 143.9 L271.7 163.6 L281.2 173.1 L284.6 190.4 L279.5 206.2 L281.0 215.2 L291.6 218.8 L301.8 233.7 L357.0 229.6 L381.9 235.1 L412.1 272.0 L429.5 267.4 L460.4 269.7 L484.9 264.8 L500.0 272.2 L492.3 295.3 L482.7 309.7 L479.4 340.5 L488.0 369.0 L500.2 381.8 L501.7 391.4 L479.9 412.8 L495.5 422.2 L506.9 437.2 L520.0 480.1 L511.9 485.3 L503.5 460.0 L491.6 446.4 L477.4 461.2 L393.8 460.2 L394.3 487.1 L419.5 491.5 L418.0 508.0 L409.4 503.5 L385.3 510.6 L385.0 541.8 L404.1 557.5 L410.8 582.0 L409.8 600.7 L390.5 718.3 L369.0 695.5 L356.2 694.5 L383.9 650.8 L351.0 630.7 L325.2 634.4 L309.7 627.0 L286.1 638.3 L254.1 633.0 L228.8 588.0 L209.0 576.9 L195.3 556.6 L166.7 536.3 L155.3 540.4 Z"

// Coordenadas de las principales ciudades (clave normalizada → [lat, lon])
const CITY_COORDS = {
  bogota: [4.65, -74.10], medellin: [6.24, -75.58], cali: [3.44, -76.52],
  barranquilla: [10.96, -74.80], bucaramanga: [7.12, -73.12], cartagena: [10.42, -75.53],
  cucuta: [7.89, -72.50], pereira: [4.81, -75.69], 'santa marta': [11.24, -74.20],
  ibague: [4.44, -75.24], pasto: [1.21, -77.28], manizales: [5.07, -75.52],
  neiva: [2.93, -75.28], villavicencio: [4.14, -73.63], armenia: [4.53, -75.68],
  valledupar: [10.46, -73.25], monteria: [8.75, -75.88], popayan: [2.44, -76.61],
  sincelejo: [9.30, -75.40], tunja: [5.54, -73.36], riohacha: [11.54, -72.91],
  florencia: [1.61, -75.61], yopal: [5.34, -72.40], quibdo: [5.69, -76.66],
  calarca: [4.53, -75.64], tulua: [4.08, -76.20], cota: [4.81, -74.10],
  girardot: [4.30, -74.80], soacha: [4.58, -74.22], palmira: [3.54, -76.30],
  buenaventura: [3.88, -77.03], zipaquira: [5.02, -73.99], mocoa: [1.15, -76.65],
  arauca: [7.08, -70.76], leticia: [-4.21, -69.94], inirida: [3.87, -67.92],
  mitu: [1.25, -70.23], 'puerto carreno': [6.19, -67.49], chia: [4.86, -74.03],
}

// NFD descompone acentos (é → e + marca) y [^a-z ] elimina las marcas y símbolos
const norm = (s) => (s || '').toLowerCase().normalize('NFD').replace(/[^a-z ]/g, '').trim()
const coordOf = (city) => CITY_COORDS[norm(city)] || null

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
  const maxCount = geo.reduce((m, g) => Math.max(m, g.count), 0) || 1
  const located = geo.filter(g => coordOf(g.city))
  const foreign = geo.filter(g => !coordOf(g.city))

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

          {/* Distribución geográfica */}
          <div className="card">
            <h2 className="font-semibold text-gray-800">Distribución geográfica de las cuentas identificadas</h2>
            <p className="text-sm text-gray-500 mt-0.5">De las {data.totals.accounts_with_city} cuentas con ciudad registrada, provienen de:</p>
            {geo.length === 0 ? (
              <div className="text-center py-12 text-gray-400">
                <MapPin className="w-10 h-10 mx-auto mb-3 opacity-30" />
                <p className="font-medium">Aún no hay cuentas con ciudad de origen</p>
                <p className="text-sm mt-1">Diligencia la "Ciudad de origen" en el perfil de cada cuenta.</p>
              </div>
            ) : (
              <div className="grid md:grid-cols-2 gap-6 mt-4">
                {/* Mapa */}
                <div className="flex justify-center">
                  <svg viewBox={`0 0 ${GEO.W} ${GEO.H}`} className="w-full max-w-[320px] h-auto">
                    <path d={COL_PATH} fill="#dbeafe" stroke="#93c5fd" strokeWidth="1.5" />
                    {located.map(g => {
                      const [lat, lon] = coordOf(g.city)
                      const [x, y] = proj(lon, lat)
                      const r = 6 + 4 * Math.sqrt(g.count)
                      return (
                        <g key={g.city}>
                          <circle cx={x} cy={y} r={r} fill="#ef4444" fillOpacity="0.55" stroke="#b91c1c" strokeWidth="1" />
                          <text x={x} y={y + 4} textAnchor="middle" fontSize="16" fontWeight="700" fill="#7f1d1d">{g.count}</text>
                          <title>{g.city}: {g.count}</title>
                        </g>
                      )
                    })}
                  </svg>
                </div>
                {/* Ranking */}
                <div className="space-y-1.5">
                  {geo.map(g => (
                    <div key={g.city} className="flex items-center gap-2">
                      <div className="w-32 shrink-0 text-sm text-gray-700 truncate flex items-center gap-1">
                        {!coordOf(g.city) && <span title="Fuera de Colombia / no ubicada">🌐</span>}
                        {g.city}
                      </div>
                      <div className="flex-1 bg-gray-100 rounded-full h-4 overflow-hidden">
                        <div className="h-full bg-primary-500 rounded-full flex items-center justify-end pr-1.5" style={{ width: `${Math.max(8, (g.count / maxCount) * 100)}%` }}>
                          <span className="text-[10px] font-bold text-white">{g.count}</span>
                        </div>
                      </div>
                    </div>
                  ))}
                  {foreign.length > 0 && (
                    <p className="text-xs text-gray-400 pt-2">🌐 Fuera de Colombia o sin ubicar en el mapa: {foreign.map(f => f.city).join(', ')}</p>
                  )}
                </div>
              </div>
            )}
          </div>

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
