import { useQuery } from '@tanstack/react-query'
import ReactECharts from 'echarts-for-react'
import { MessageSquare, TrendingDown, Bot, Building2, AlertTriangle } from 'lucide-react'
import { format } from 'date-fns'
import { es } from 'date-fns/locale'
import client from '../../../shared/api/client'

const SOV_COLORS = ['#6366f1','#f59e0b','#10b981','#ef4444','#3b82f6','#8b5cf6','#ec4899','#14b8a6']

function StatCard({ icon: Icon, label, value, sub, color = 'primary' }) {
  const colors = {
    primary: 'bg-primary-50 text-primary-600',
    red:     'bg-red-50 text-red-600',
    yellow:  'bg-yellow-50 text-yellow-600',
    green:   'bg-green-50 text-green-600',
  }
  return (
    <div className="card flex items-start gap-4">
      <div className={`rounded-xl p-3 ${colors[color]}`}>
        <Icon className="w-5 h-5" />
      </div>
      <div>
        <p className="text-2xl font-bold text-gray-900">{value ?? '—'}</p>
        <p className="text-sm font-medium text-gray-700">{label}</p>
        {sub && <p className="text-xs text-gray-400 mt-0.5">{sub}</p>}
      </div>
    </div>
  )
}

export default function Dashboard() {
  const { data, isLoading } = useQuery({
    queryKey: ['dashboard'],
    queryFn: () => client.get('/dashboard').then(r => r.data),
  })

  const timelineOption = {
    tooltip: { trigger: 'axis' },
    legend: { data: ['Negativas', 'Neutras', 'Positivas'], bottom: 0 },
    grid: { top: 10, bottom: 40, left: 40, right: 20 },
    xAxis: { type: 'category', data: data?.timeline?.dates ?? [], axisLabel: { fontSize: 11 } },
    yAxis: { type: 'value', axisLabel: { fontSize: 11 } },
    series: [
      { name: 'Negativas', type: 'bar', stack: 'total', data: data?.timeline?.negative  ?? [], color: '#ef4444' },
      { name: 'Neutras',   type: 'bar', stack: 'total', data: data?.timeline?.neutral   ?? [], color: '#d1d5db' },
      { name: 'Positivas', type: 'bar', stack: 'total', data: data?.timeline?.positive  ?? [], color: '#22c55e' },
    ],
  }

  const sentimentOption = {
    tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
    series: [{
      type: 'pie', radius: ['45%', '75%'],
      data: [
        { value: data?.sentiment?.very_negative ?? 0, name: 'Muy negativo', itemStyle: { color: '#dc2626' } },
        { value: data?.sentiment?.negative      ?? 0, name: 'Negativo',     itemStyle: { color: '#f97316' } },
        { value: data?.sentiment?.neutral       ?? 0, name: 'Neutral',      itemStyle: { color: '#9ca3af' } },
        { value: data?.sentiment?.positive      ?? 0, name: 'Positivo',     itemStyle: { color: '#22c55e' } },
      ],
      label: { fontSize: 11 },
    }],
  }

  if (isLoading) return <div className="flex items-center justify-center h-64 text-gray-400">Cargando dashboard...</div>

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
        <p className="text-gray-500 text-sm mt-0.5">
          {format(new Date(), "EEEE d 'de' MMMM yyyy", { locale: es })}
        </p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
        <StatCard icon={MessageSquare} label="Menciones hoy"
          value={data?.stats?.today_mentions} color="primary" />
        <StatCard icon={TrendingDown} label="Menciones negativas"
          value={data?.stats?.negative_pct != null ? data.stats.negative_pct + '%' : '—'}
          color="red" />
        <StatCard icon={Bot} label="Bots detectados"
          value={data?.stats?.bots_today} color="yellow" />
        <StatCard icon={Building2} label="Entidades activas"
          value={data?.stats?.active_entities} sub="monitoreadas" color="green" />
      </div>

      {data?.recent_alerts?.length > 0 && (
        <div className="card">
          <div className="flex items-center gap-2 mb-4">
            <AlertTriangle className="w-4 h-4 text-red-500" />
            <h2 className="font-semibold text-gray-800">Alertas recientes</h2>
          </div>
          <div className="space-y-2">
            {data.recent_alerts.map(alert => (
              <div key={alert.id} className="flex items-start gap-3 p-3 rounded-lg bg-gray-50">
                <span className={`badge badge-${alert.severity} shrink-0 mt-0.5`}>
                  {alert.severity.toUpperCase()}
                </span>
                <div className="min-w-0">
                  <p className="text-sm font-medium text-gray-800 truncate">{alert.entity_name}</p>
                  <p className="text-xs text-gray-500 truncate">{alert.message}</p>
                </div>
                <span className="text-xs text-gray-400 shrink-0 ml-auto">
                  {format(new Date(alert.triggered_at), 'HH:mm')}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        <div className="card xl:col-span-2">
          <h2 className="font-semibold text-gray-800 mb-4">Menciones por día — últimos 14 días</h2>
          <ReactECharts option={timelineOption} style={{ height: 240 }} />
        </div>
        <div className="card">
          <h2 className="font-semibold text-gray-800 mb-4">Distribución de sentimiento</h2>
          <ReactECharts option={sentimentOption} style={{ height: 240 }} />
        </div>
      </div>
    </div>
  )
}
