import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import ReactECharts from 'echarts-for-react'
import { GitCompareArrows } from 'lucide-react'
import client from '../api/client'
import InfoTip from '../components/InfoTip'

const fetchEntities = () => client.get('/entities').then(r => r.data)
const fetchCompare  = (ids, days) =>
  client.get('/dashboard/compare', { params: { entity_ids: ids.join(','), days } }).then(r => r.data)

const COLORS = ['#6366f1', '#f59e0b', '#10b981', '#ef4444']

const PLATFORM_ICON = { twitter: '🐦', reddit: '🤖', youtube: '▶️', instagram: '📸', facebook: '👥', rss: '📰' }

// 'AAAA-MM-DD' → 'DD/MM/AAAA'
const fmtDay = (d) => (d ? d.split('-').reverse().join('/') : '')

// Definiciones: son las mismas del Dashboard y del detalle de cada entidad
const TIPS = {
  mentions: 'Publicaciones que coinciden con las keywords parametrizadas de la entidad, en el período. Es la misma cifra que «Total N días» del detalle de la entidad. El número gris son los autores distintos.',
  negative: 'Porcentaje de menciones negativas o muy negativas sobre las menciones ya CLASIFICADAS (con sentimiento). Las «sin clasificar» (baja confianza del modelo) no cuentan ni como positivas ni como negativas. Mismo criterio del Dashboard.',
  bots: 'Cuentas DISTINTAS que publicaron sobre la entidad en el período y cuyo puntaje de bot alcanza el umbral (por defecto 70 %). Es una estimación por reglas sobre el perfil, no un modelo entrenado. Mismo criterio del Dashboard.',
  urgency: 'Promedio del puntaje de urgencia (0-100) de las menciones ya procesadas. Combina sentimiento (35 %), discurso de odio (35 %) y alcance (30 %). Verde < 30 · naranja 30-59 · rojo ≥ 60.',
  platform: 'Red social con más menciones de la entidad en el período.',
}

export default function Compare() {
  const [days,     setDays]     = useState(7)
  const [selected, setSelected] = useState([])

  const { data: entities = [] } = useQuery({ queryKey: ['entities'], queryFn: fetchEntities })

  const { data: compareData, isLoading } = useQuery({
    queryKey: ['compare', selected, days],
    queryFn:  () => fetchCompare(selected, days),
    enabled:  selected.length >= 2,
  })

  const items = compareData?.entities ?? []
  const threshold = Math.round((compareData?.bot_threshold ?? 0.7) * 100)

  const toggleEntity = (id) => {
    if (selected.includes(id)) {
      setSelected(s => s.filter(x => x !== id))
    } else if (selected.length < 4) {
      setSelected(s => [...s, id])
    }
  }

  // Opciones ECharts para gráfico de barras comparativo
  const volumeOption = {
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    grid: { top: 10, bottom: 50, left: 40, right: 20 },
    xAxis: { type: 'category', data: items.map(e => e.entity_name), axisLabel: { fontSize: 11, interval: 0, rotate: 15 } },
    yAxis: { type: 'value', axisLabel: { fontSize: 11 } },
    series: [
      {
        name: 'Menciones', type: 'bar',
        data: items.map((e, i) => ({ value: e.total_mentions, itemStyle: { color: COLORS[i] } })),
        label: { show: true, position: 'top', fontSize: 11 },
      },
    ],
  }

  const sentimentOption = {
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    legend: { bottom: 0, textStyle: { fontSize: 11 } },
    grid: { top: 10, bottom: 50, left: 40, right: 20 },
    xAxis: { type: 'category', data: items.map(e => e.entity_name), axisLabel: { fontSize: 11, interval: 0, rotate: 15 } },
    yAxis: { type: 'value', axisLabel: { fontSize: 11 }, max: 100 },
    series: [
      {
        name: '% Negativo (sobre clasificadas)', type: 'bar',
        data: items.map(e => e.negative_pct),
        color: '#ef4444',
        label: { show: true, position: 'top', fontSize: 10, formatter: '{c}%' },
      },
    ],
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Comparar alertas</h1>
        <p className="text-gray-500 text-sm mt-0.5">Benchmarking de métricas entre entidades monitoreadas</p>
      </div>

      {/* Selector */}
      <div className="card py-4 space-y-3">
        <div className="flex items-center justify-between flex-wrap gap-2">
          <div>
            <p className="text-sm font-medium text-gray-700">Selecciona 2-4 entidades para comparar</p>
            <p className="text-xs text-gray-400">{selected.length} seleccionadas (máx. 4)</p>
          </div>
          <div className="flex items-center gap-2">
            <select className="input w-auto" value={days} onChange={e => setDays(Number(e.target.value))}>
              <option value={7}>Últimos 7 días</option>
              <option value={14}>Últimos 14 días</option>
              <option value={30}>Últimos 30 días</option>
            </select>
          </div>
        </div>
        {compareData?.date_from && (
          <p className="text-xs text-gray-400">
            Período comparado: <span className="font-medium text-gray-500">{fmtDay(compareData.date_from)} – {fmtDay(compareData.date_to)}</span>{' '}
            (días calendario, hora de Colombia; incluye hoy). Mismo período que «Total {days} días» del detalle de cada entidad.
          </p>
        )}
        <div className="flex flex-wrap gap-2">
          {entities.map(e => {
            const idx      = selected.indexOf(e.id)
            const isActive = idx >= 0
            return (
              <button
                key={e.id}
                onClick={() => toggleEntity(e.id)}
                disabled={!isActive && selected.length >= 4}
                className={`px-3 py-1.5 rounded-full text-sm font-medium border transition-all ${
                  isActive
                    ? 'text-white border-transparent'
                    : 'bg-white text-gray-600 border-gray-200 hover:border-gray-400 disabled:opacity-40 disabled:cursor-not-allowed'
                }`}
                style={isActive ? { background: COLORS[idx], borderColor: COLORS[idx] } : {}}
              >
                {e.name}
              </button>
            )
          })}
        </div>
      </div>

      {selected.length < 2 ? (
        <div className="card text-center py-16 text-gray-400">
          <GitCompareArrows className="w-10 h-10 mx-auto mb-3 opacity-30" />
          <p className="font-medium">Selecciona al menos 2 entidades</p>
        </div>
      ) : isLoading ? (
        <div className="text-center text-gray-400 py-12">Comparando entidades...</div>
      ) : items.length > 0 ? (
        <>
          {/* Gráficas comparativas */}
          <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
            <div className="card">
              <h2 className="font-semibold text-gray-800 mb-4 flex items-center gap-1.5">
                Volumen de menciones <InfoTip text={TIPS.mentions} align="left" />
              </h2>
              <ReactECharts option={volumeOption} style={{ height: 220 }} />
            </div>
            <div className="card">
              <h2 className="font-semibold text-gray-800 mb-4 flex items-center gap-1.5">
                % Menciones negativas <InfoTip text={TIPS.negative} align="left" />
              </h2>
              <ReactECharts option={sentimentOption} style={{ height: 220 }} />
            </div>
          </div>

          {/* Tabla detallada */}
          <div className="card overflow-x-auto sm:overflow-visible">
            <h2 className="font-semibold text-gray-800 mb-4">Comparativa detallada</h2>
            <table className="min-w-[560px] w-full text-sm">
              <thead>
                <tr className="text-xs text-gray-500 border-b">
                  <th className="text-left pb-2 font-medium">Entidad</th>
                  <th className="text-right pb-2 font-medium">Menciones <InfoTip text={TIPS.mentions} below /></th>
                  <th className="text-right pb-2 font-medium">% Negativo <InfoTip text={TIPS.negative} below /></th>
                  <th className="text-right pb-2 font-medium">Bots detectados <InfoTip text={TIPS.bots} below /></th>
                  <th className="text-right pb-2 font-medium">Urgencia promedio <InfoTip text={TIPS.urgency} below align="right" /></th>
                  <th className="text-center pb-2 font-medium">Red principal <InfoTip text={TIPS.platform} below align="right" /></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {items.map((item, i) => (
                  <tr key={item.entity_id} className="hover:bg-gray-50">
                    <td className="py-3 font-medium text-gray-800 flex items-center gap-2">
                      <span className="w-3 h-3 rounded-full shrink-0" style={{ background: COLORS[i] }} />
                      {item.entity_name}
                    </td>
                    <td className="py-3 text-right text-gray-700">
                      {item.total_mentions.toLocaleString()}
                      <div className="text-[11px] text-gray-400">{item.authors_count.toLocaleString()} autores</div>
                    </td>
                    <td className={`py-3 text-right font-semibold ${item.negative_pct >= 50 ? 'text-red-600' : item.negative_pct >= 30 ? 'text-yellow-600' : 'text-green-600'}`}>
                      {item.negative_pct}%
                      <div className="text-[11px] font-normal text-gray-400">
                        {item.negative_count} de {item.classified.toLocaleString()} clasificadas
                        {item.unclassified > 0 && ` · ${item.unclassified} sin clasificar`}
                      </div>
                    </td>
                    <td className="py-3 text-right text-gray-700">
                      {item.bot_count.toLocaleString()}
                      <div className="text-[11px] text-gray-400">cuentas · puntaje ≥ {threshold} %</div>
                    </td>
                    <td className={`py-3 text-right font-semibold ${item.avg_urgency >= 60 ? 'text-red-600' : item.avg_urgency >= 30 ? 'text-yellow-600' : 'text-gray-600'}`}>
                      {item.avg_urgency}
                      <div className="text-[11px] font-normal text-gray-400">de 100</div>
                    </td>
                    <td className="py-3 text-center">
                      {item.top_platform
                        ? <span title={item.top_platform}>{PLATFORM_ICON[item.top_platform] ?? '🌐'} {item.top_platform}</span>
                        : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      ) : null}
    </div>
  )
}
