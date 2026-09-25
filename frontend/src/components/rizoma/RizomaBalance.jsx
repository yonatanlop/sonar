/**
 * Rizoma › Balance de denuncias
 * Denuncias hechas y publicaciones / cuentas / grupos cerrados, por día, semana o mes
 * (días calendario de Colombia), con filtro por tipo de red.
 */
import { useState } from 'react'
import { useQuery, keepPreviousData } from '@tanstack/react-query'
import ReactECharts from 'echarts-for-react'
import { AlertTriangle } from 'lucide-react'
import client from '../../api/client'
import InfoTip from '../InfoTip'
import { MEDIUMS, MEDIUM_BADGE, bucketLabel, fmtIsoDay } from './shared'

const fetchBalance = (p) => client.get('/case-reports/balance', { params: p }).then(r => r.data)

const GRANULARITY = [
  { key: 'day',   label: 'Día' },
  { key: 'week',  label: 'Semana' },
  { key: 'month', label: 'Mes' },
]

const TIPS = {
  reported: 'Publicaciones marcadas como denunciadas, contadas en la fecha de la denuncia.',
  removed: 'Publicaciones que se marcaron como eliminadas, contadas en la fecha de eliminación.',
  accounts: 'Cuentas de atacantes marcadas como cerradas, contadas en la fecha de cierre.',
  groups: 'Grupos de Facebook cerrados (fecha fin del registro en «Grupos a cerrar»). Se muestran los de Facebook o todas las redes.',
  rate: 'De todas las publicaciones denunciadas (sin importar la fecha), qué porcentaje ya fue eliminado.',
}

function Kpi({ label, value, sub, color, tip }) {
  return (
    <div className="card text-center">
      <p className={`text-2xl font-bold ${color}`}>{value}</p>
      <p className="text-xs text-gray-500 mt-0.5 flex items-center justify-center gap-1">{label} {tip && <InfoTip text={tip} />}</p>
      {sub && <p className="text-[11px] text-gray-400 mt-0.5">{sub}</p>}
    </div>
  )
}

export default function RizomaBalance() {
  const [granularity, setGranularity] = useState('week')
  const [medium, setMedium]           = useState('')
  const [dateFrom, setDateFrom]       = useState('')
  const [dateTo, setDateTo]           = useState('')

  const { data, isLoading, error } = useQuery({
    queryKey: ['rz-balance', granularity, medium, dateFrom, dateTo],
    queryFn: () => fetchBalance({ granularity, medium, date_from: dateFrom, date_to: dateTo }),
    placeholderData: keepPreviousData,
  })

  const points = data?.points ?? []
  const labels = points.map(p => bucketLabel(p.start, granularity))
  const showGroups = !medium || medium === 'Facebook'

  const series = [
    { name: 'Denuncias', key: 'reported', color: '#f59e0b' },
    { name: 'Publicaciones eliminadas', key: 'posts_removed', color: '#10b981' },
    { name: 'Cuentas cerradas', key: 'accounts_closed', color: '#ef4444' },
    ...(showGroups ? [{ name: 'Grupos cerrados', key: 'groups_closed', color: '#6366f1' }] : []),
  ]
  const option = {
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    legend: { bottom: 0, textStyle: { fontSize: 11 } },
    grid: { top: 16, bottom: 50, left: 40, right: 16 },
    xAxis: { type: 'category', data: labels, axisLabel: { fontSize: 11, interval: 'auto', rotate: labels.length > 14 ? 40 : 0 } },
    yAxis: { type: 'value', minInterval: 1, axisLabel: { fontSize: 11 } },
    series: series.map(s => ({
      name: s.name, type: 'bar', color: s.color,
      data: points.map(p => p[s.key]),
    })),
  }

  const t = data?.totals
  const undated = data?.undated
  const undatedTotal = undated ? undated.reported + undated.posts_removed + undated.accounts_closed : 0

  return (
    <div className="space-y-4">
      {/* Controles */}
      <div className="card py-3 space-y-3">
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex rounded-lg border border-gray-200 overflow-hidden">
            {GRANULARITY.map(g => (
              <button key={g.key} onClick={() => setGranularity(g.key)}
                className={`px-4 py-1.5 text-sm font-medium ${granularity === g.key ? 'bg-primary-600 text-white' : 'bg-white text-gray-600 hover:bg-gray-50'}`}>
                {g.label}
              </button>
            ))}
          </div>
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
            Período: <span className="font-medium text-gray-500">{fmtIsoDay(data.date_from)} – {fmtIsoDay(data.date_to)}</span>
            {' '}(hora de Colombia; por defecto {granularity === 'day' ? '30 días' : granularity === 'week' ? '12 semanas' : '12 meses'}).
            {granularity === 'week' && ' Las semanas empiezan el lunes.'}
          </p>
        )}
      </div>

      {error ? (
        <div className="card text-center text-red-600 py-8 text-sm">No se pudo cargar el balance. Revisa las fechas e inténtalo de nuevo.</div>
      ) : isLoading ? (
        <div className="text-center text-gray-400 py-12">Calculando balance…</div>
      ) : data && (
        <>
          <div className={`grid grid-cols-2 ${showGroups ? 'lg:grid-cols-5' : 'lg:grid-cols-4'} gap-4`}>
            <Kpi label="Denuncias" value={t.reported} color="text-amber-600" tip={TIPS.reported} sub="en el período" />
            <Kpi label="Publicaciones eliminadas" value={t.posts_removed} color="text-green-600" tip={TIPS.removed} sub="en el período" />
            <Kpi label="Cuentas cerradas" value={t.accounts_closed} color="text-red-600" tip={TIPS.accounts} sub="en el período" />
            {showGroups && <Kpi label="Grupos cerrados" value={t.groups_closed} color="text-indigo-600" tip={TIPS.groups}
              sub={`${t.groups_started} iniciados`} />}
            <Kpi label="Tasa de eliminación" value={`${data.overall.removal_rate}%`} color="text-gray-800" tip={TIPS.rate}
              sub={`${data.overall.reported_removed} de ${data.overall.reported} denunciadas · histórico`} />
          </div>

          {undatedTotal > 0 && (
            <div className="flex gap-2 items-start text-sm bg-amber-50 border border-amber-100 text-amber-800 rounded-lg px-4 py-3">
              <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0" />
              <p>
                Hay registros históricos <b>sin fecha</b> que no aparecen en la gráfica:{' '}
                {undated.reported} denuncias, {undated.posts_removed} publicaciones eliminadas y {undated.accounts_closed} cuentas cerradas.
                Al editarlos y ponerles fecha en <b>Seguimiento a caso</b> se sumarán al período correspondiente.
                Los nuevos registros toman la fecha de hoy automáticamente.
              </p>
            </div>
          )}

          <div className="card">
            <h2 className="font-semibold text-gray-800 mb-3">
              Balance por {granularity === 'day' ? 'día' : granularity === 'week' ? 'semana' : 'mes'}
            </h2>
            <ReactECharts option={option} style={{ height: 300 }} notMerge />
          </div>

          <div className="card p-0 overflow-hidden">
            <div className="px-5 py-3 border-b border-gray-100">
              <h2 className="font-semibold text-gray-800">Por tipo de red</h2>
              <p className="text-xs text-gray-400">Movimientos dentro del período; «Cuentas» es el total registrado.</p>
            </div>
            {data.by_medium.length === 0 ? (
              <p className="text-center text-gray-400 py-8 text-sm">Sin cuentas registradas.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-gray-50 border-b border-gray-100">
                    <tr className="text-gray-600">
                      <th className="text-left px-5 py-2.5 font-medium">Red</th>
                      <th className="text-right px-5 py-2.5 font-medium">Cuentas</th>
                      <th className="text-right px-5 py-2.5 font-medium">Denuncias</th>
                      <th className="text-right px-5 py-2.5 font-medium">Eliminadas</th>
                      <th className="text-right px-5 py-2.5 font-medium">Cuentas cerradas</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {data.by_medium.map(m => (
                      <tr key={m.medium} className="hover:bg-gray-50">
                        <td className="px-5 py-2.5"><span className={`badge ${MEDIUM_BADGE[m.medium] || 'bg-gray-100 text-gray-600'}`}>{m.medium}</span></td>
                        <td className="px-5 py-2.5 text-right text-gray-700">{m.accounts}</td>
                        <td className="px-5 py-2.5 text-right text-amber-600 font-medium">{m.reported}</td>
                        <td className="px-5 py-2.5 text-right text-green-600 font-medium">{m.posts_removed}</td>
                        <td className="px-5 py-2.5 text-right text-red-600 font-medium">{m.accounts_closed}</td>
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
