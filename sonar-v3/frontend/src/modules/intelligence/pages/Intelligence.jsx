import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import ReactECharts from 'echarts-for-react'
import { format } from 'date-fns'
import { es } from 'date-fns/locale'
import { Activity, TrendingUp, FileText } from 'lucide-react'
import client from '../../../shared/api/client'

const fetchAnomalies = () => client.get('/intelligence/anomalies').then(r => r.data)
const fetchTrends    = () => client.get('/intelligence/trends').then(r => r.data)
const fetchSummaries = () => client.get('/intelligence/summaries').then(r => r.data)

function TabBtn({ active, onClick, children }) {
  return (
    <button
      onClick={onClick}
      className={`px-4 py-2 text-sm font-medium rounded-lg transition-colors ${
        active ? 'bg-primary-600 text-white' : 'text-gray-600 hover:bg-gray-100'
      }`}
    >
      {children}
    </button>
  )
}

export default function Intelligence() {
  const [tab, setTab] = useState('anomalies')

  const { data: anomalies = [], isLoading: loadA } = useQuery({ queryKey: ['anomalies'], queryFn: fetchAnomalies })
  const { data: trends    = [], isLoading: loadT } = useQuery({ queryKey: ['trends'],    queryFn: fetchTrends })
  const { data: summaries = [], isLoading: loadS } = useQuery({ queryKey: ['summaries'], queryFn: fetchSummaries })

  const trendOption = (t) => ({
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'category', data: t.dates ?? [], axisLabel: { fontSize: 10 } },
    yAxis: { type: 'value', axisLabel: { fontSize: 10 } },
    grid: { top: 10, bottom: 30, left: 40, right: 20 },
    series: [
      { type: 'line', data: t.actual       ?? [], name: 'Real',     color: '#6366f1', smooth: true },
      { type: 'line', data: t.predicted    ?? [], name: 'Forecast', color: '#f59e0b', smooth: true, lineStyle: { type: 'dashed' } },
    ],
  })

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-gray-900">Inteligencia</h1>

      <div className="flex gap-2">
        <TabBtn active={tab === 'anomalies'} onClick={() => setTab('anomalies')}>
          <Activity className="w-4 h-4 inline mr-1" /> Anomalías
        </TabBtn>
        <TabBtn active={tab === 'trends'} onClick={() => setTab('trends')}>
          <TrendingUp className="w-4 h-4 inline mr-1" /> Tendencias
        </TabBtn>
        <TabBtn active={tab === 'summaries'} onClick={() => setTab('summaries')}>
          <FileText className="w-4 h-4 inline mr-1" /> Resúmenes
        </TabBtn>
      </div>

      {tab === 'anomalies' && (
        loadA ? <div className="text-center text-gray-400 py-12">Cargando...</div> : (
          <div className="space-y-3">
            {anomalies.length === 0 && (
              <div className="text-center text-gray-400 py-12">Sin anomalías detectadas</div>
            )}
            {anomalies.map(a => (
              <div key={a.id} className="card p-4">
                <div className="flex items-center justify-between mb-2">
                  <span className="font-medium text-gray-900">{a.entity_name}</span>
                  <span className={`badge badge-${a.severity ?? 'medium'}`}>{a.anomaly_type}</span>
                </div>
                <div className="grid grid-cols-3 gap-4 text-sm">
                  <div>
                    <p className="text-xs text-gray-400">Valor observado</p>
                    <p className="font-semibold">{a.observed_value}</p>
                  </div>
                  <div>
                    <p className="text-xs text-gray-400">Valor esperado</p>
                    <p className="font-semibold">{a.expected_value?.toFixed(1)}</p>
                  </div>
                  <div>
                    <p className="text-xs text-gray-400">Z-score</p>
                    <p className="font-semibold">{a.z_score?.toFixed(2)}</p>
                  </div>
                </div>
                <p className="text-xs text-gray-400 mt-2">
                  {format(new Date(a.detected_at), "d MMM yyyy HH:mm", { locale: es })}
                </p>
              </div>
            ))}
          </div>
        )
      )}

      {tab === 'trends' && (
        loadT ? <div className="text-center text-gray-400 py-12">Cargando...</div> : (
          <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
            {trends.length === 0 && (
              <div className="text-center text-gray-400 py-12 col-span-2">Sin datos de tendencias</div>
            )}
            {trends.map(t => (
              <div key={t.entity_id} className="card">
                <h3 className="font-medium text-gray-900 mb-3">{t.entity_name}</h3>
                <ReactECharts option={trendOption(t)} style={{ height: 180 }} />
              </div>
            ))}
          </div>
        )
      )}

      {tab === 'summaries' && (
        loadS ? <div className="text-center text-gray-400 py-12">Cargando...</div> : (
          <div className="space-y-4">
            {summaries.length === 0 && (
              <div className="text-center text-gray-400 py-12">Sin resúmenes generados</div>
            )}
            {summaries.map(s => (
              <div key={s.id} className="card">
                <div className="flex items-center justify-between mb-3">
                  <div>
                    <h3 className="font-medium text-gray-900">{s.entity_name}</h3>
                    <p className="text-xs text-gray-400">
                      {format(new Date(s.summary_date), "d 'de' MMMM yyyy", { locale: es })}
                      {' · '}{s.mention_count} menciones · {s.model_used}
                    </p>
                  </div>
                </div>
                <p className="text-sm text-gray-700 leading-relaxed">{s.summary_text}</p>
              </div>
            ))}
          </div>
        )
      )}
    </div>
  )
}
