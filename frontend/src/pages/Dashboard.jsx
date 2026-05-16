import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import ReactECharts from 'echarts-for-react'
import { TrendingUp, TrendingDown, MessageSquare, AlertTriangle, Bot, Building2, Minus } from 'lucide-react'
import client from '../api/client'
import { format } from 'date-fns'
import { es } from 'date-fns/locale'

const fetchDashboard = () => client.get('/dashboard').then(r => r.data)
const fetchSOV       = (days) => client.get('/dashboard/share-of-voice', { params: { days } }).then(r => r.data)

function DeltaBadge({ delta }) {
  if (!delta) return null
  const { delta_pct, trend } = delta
  if (trend === 'stable') return <span className="text-xs text-gray-400 flex items-center gap-0.5"><Minus className="w-3 h-3" /> sin cambio</span>
  const up = trend === 'up'
  return (
    <span className={`text-xs flex items-center gap-0.5 font-medium ${up ? 'text-red-500' : 'text-green-600'}`}>
      {up ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
      {up ? '+' : ''}{delta_pct}% vs ayer
    </span>
  )
}

function StatCard({ icon: Icon, label, value, delta, sub, color = 'primary', onClick }) {
  const colors = {
    primary: 'bg-primary-50 text-primary-600',
    red:     'bg-red-50 text-red-600',
    yellow:  'bg-yellow-50 text-yellow-600',
    green:   'bg-green-50 text-green-600',
  }
  return (
    <div
      className={`card flex items-start gap-4 ${onClick ? 'cursor-pointer hover:shadow-md transition-shadow' : ''}`}
      onClick={onClick}
    >
      <div className={`rounded-xl p-3 ${colors[color]}`}>
        <Icon className="w-5 h-5" />
      </div>
      <div>
        <p className="text-2xl font-bold text-gray-900">{value ?? '—'}</p>
        <p className="text-sm font-medium text-gray-700">{label}</p>
        {onClick && <p className="text-xs text-blue-500 mt-0.5">Ver detalle →</p>}
        {delta && <DeltaBadge delta={delta} />}
        {sub && !delta && <p className="text-xs text-gray-400 mt-0.5">{sub}</p>}
      </div>
    </div>
  )
}

function MentionRow({ m }) {
  const sentimentColor = {
    very_negative: 'text-red-600',
    negative:      'text-orange-500',
    neutral:       'text-gray-500',
    positive:      'text-green-600',
  }[m.sentiment_label] ?? 'text-gray-500'

  return (
    <div className="border-b border-gray-100 py-3 px-4 hover:bg-gray-50">
      <div className="flex justify-between items-start gap-2 mb-1">
        <span className="text-xs font-medium text-gray-700 truncate">
          @{m.author_username ?? 'anónimo'} · {m.platform_name}
        </span>
        <span className={`text-xs font-semibold shrink-0 ${sentimentColor}`}>
          {m.sentiment_label?.replace('_', ' ')}
        </span>
      </div>
      <p className="text-sm text-gray-800 line-clamp-2">{m.content}</p>
      {m.url && (
        <a href={m.url} target="_blank" rel="noreferrer"
          className="text-xs text-blue-500 hover:underline mt-1 inline-block">
          Ver publicación ↗
        </a>
      )}
    </div>
  )
}

const SOV_COLORS = ['#6366f1','#f59e0b','#10b981','#ef4444','#3b82f6','#8b5cf6','#ec4899','#14b8a6']

export default function Dashboard() {
  const [sovDays, setSovDays] = useState(7)
  const [drawer, setDrawer]   = useState(null)

  const { data, isLoading } = useQuery({ queryKey: ['dashboard'], queryFn: fetchDashboard })
  const { data: sovData }   = useQuery({ queryKey: ['sov', sovDays], queryFn: () => fetchSOV(sovDays) })
  const drawerKey = drawer ? JSON.stringify(drawer.params) : null
  const { data: drawerData, isFetching: drawerFetching, isError: drawerError } = useQuery({
    queryKey: ['drawer-mentions', drawerKey],
    queryFn:  () => client.get('/mentions', { params: { ...drawer.params, page: 1 } }).then(r => r.data),
    enabled:  !!drawer,
    staleTime: 0,
  })

  // Gráfica: menciones por día (últimos 14 días)
  const timelineOption = {
    tooltip: { trigger: 'axis' },
    legend: { data: ['Negativas', 'Neutras', 'Positivas'], bottom: 0 },
    grid: { top: 10, bottom: 40, left: 40, right: 20 },
    xAxis: {
      type: 'category',
      data: data?.timeline?.dates ?? [],
      axisLabel: { fontSize: 11 },
    },
    yAxis: { type: 'value', axisLabel: { fontSize: 11 } },
    series: [
      { name: 'Negativas',  type: 'bar', stack: 'total', data: data?.timeline?.negative  ?? [], color: '#ef4444' },
      { name: 'Neutras',    type: 'bar', stack: 'total', data: data?.timeline?.neutral   ?? [], color: '#d1d5db' },
      { name: 'Positivas',  type: 'bar', stack: 'total', data: data?.timeline?.positive  ?? [], color: '#22c55e' },
    ],
  }

  // Gráfica: distribución de sentimiento (torta)
  const sentimentOption = {
    tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
    series: [{
      type: 'pie',
      radius: ['45%', '75%'],
      data: [
        { value: data?.sentiment?.very_negative ?? 0, name: 'Muy negativo', itemStyle: { color: '#dc2626' } },
        { value: data?.sentiment?.negative      ?? 0, name: 'Negativo',     itemStyle: { color: '#f97316' } },
        { value: data?.sentiment?.neutral       ?? 0, name: 'Neutral',      itemStyle: { color: '#9ca3af' } },
        { value: data?.sentiment?.positive      ?? 0, name: 'Positivo',     itemStyle: { color: '#22c55e' } },
      ],
      label: { fontSize: 11 },
    }],
  }

  // Gráfica: % bots por plataforma (donut)
  const PLATFORM_ICON = { twitter: '🐦', reddit: '🤖', youtube: '▶️', rss: '📰', telegram: '✈️' }
  const botPlatformOption = {
    tooltip: {
      trigger: 'item',
      formatter: (p) => `${p.name}<br/>Bots: ${p.data.bots} / ${p.data.total} (${p.data.value}%)`,
    },
    legend: { bottom: 0, textStyle: { fontSize: 11 } },
    series: [{
      type: 'pie',
      radius: ['40%', '68%'],
      label: { show: false },
      data: (data?.bots_by_platform ?? []).map(p => ({
        name:  `${PLATFORM_ICON[p.code] ?? '🌐'} ${p.platform}`,
        value: p.bot_pct,
        bots:  p.bots,
        total: p.total,
        code:  p.code,
        itemStyle: { color: { twitter: '#1DA1F2', reddit: '#FF4500', youtube: '#FF0000', rss: '#FFA500', telegram: '#2CA5E0' }[p.code] ?? '#6B7280' },
      })),
    }],
  }

  // Gráfica: top 5 entidades con más menciones negativas
  const topEntitiesOption = {
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    grid: { top: 10, bottom: 40, left: 120, right: 20 },
    xAxis: { type: 'value', axisLabel: { fontSize: 11 } },
    yAxis: {
      type: 'category',
      data: data?.top_entities?.map(e => e.name) ?? [],
      axisLabel: { fontSize: 11 },
    },
    series: [{
      type: 'bar',
      data: data?.top_entities?.map(e => e.negative_count) ?? [],
      color: '#ef4444',
      label: { show: true, position: 'right', fontSize: 11 },
    }],
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64 text-gray-400">
        Cargando dashboard...
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Encabezado */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
        <p className="text-gray-500 text-sm mt-0.5">
          {format(new Date(), "EEEE d 'de' MMMM yyyy", { locale: es })}
        </p>
      </div>

      {/* Tarjetas de métricas con deltas */}
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
        <StatCard icon={MessageSquare} label="Menciones hoy"
          value={data?.stats?.today_mentions?.value}
          delta={data?.stats?.today_mentions}
          color="primary" />
        <StatCard icon={TrendingDown} label="Menciones negativas"
          value={data?.stats?.negative_pct?.value != null ? data.stats.negative_pct.value + '%' : '—'}
          delta={data?.stats?.negative_pct}
          color="red"
          onClick={() => setDrawer({ title: 'Menciones negativas', params: { sentiment: 'negative' } })} />
        <StatCard icon={Bot} label="Bots detectados"
          value={data?.stats?.bots_today?.value}
          delta={data?.stats?.bots_today}
          color="yellow"
          onClick={() => setDrawer({ title: 'Posibles bots detectados', params: { min_bot_score: 0.7 } })} />
        <StatCard icon={Building2} label="Entidades activas"
          value={data?.stats?.active_entities}
          sub="monitoreadas"
          color="green" />
      </div>

      {/* Alertas recientes */}
      {data?.recent_alerts?.length > 0 && (
        <div className="card">
          <div className="flex items-center gap-2 mb-4">
            <AlertTriangle className="w-4 h-4 text-red-500" />
            <h2 className="font-semibold text-gray-800">Alertas recientes</h2>
          </div>
          <div className="space-y-2">
            {data.recent_alerts.map((alert) => (
              <div key={alert.id}
                className="flex items-start gap-3 p-3 rounded-lg bg-gray-50 hover:bg-gray-100 cursor-pointer">
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

      {/* Gráficas */}
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

      {/* Share of Voice */}
      <div className="card">
        <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
          <div>
            <h2 className="font-semibold text-gray-800">Share of Voice</h2>
            <p className="text-xs text-gray-400">% de menciones por entidad sobre el total del período</p>
          </div>
          <select className="input w-auto text-sm" value={sovDays} onChange={e => setSovDays(Number(e.target.value))}>
            <option value={7}>Últimos 7 días</option>
            <option value={14}>Últimos 14 días</option>
            <option value={30}>Últimos 30 días</option>
          </select>
        </div>
        {sovData?.items?.length > 0 ? (
          <div className="grid grid-cols-1 xl:grid-cols-2 gap-4 items-center">
            <ReactECharts
              option={{
                tooltip: { trigger: 'item', formatter: '{b}: {c}% ({d}% del total)' },
                series: [{
                  type: 'pie', radius: ['40%', '70%'],
                  label: { fontSize: 11 },
                  data: sovData.items.map((item, i) => ({
                    name:  item.entity_name,
                    value: item.pct,
                    itemStyle: { color: SOV_COLORS[i % SOV_COLORS.length] },
                  })),
                }],
              }}
              style={{ height: 200 }}
            />
            <div className="space-y-2">
              {sovData.items.map((item, i) => (
                <div key={item.entity_id} className="flex items-center gap-2">
                  <span className="w-2.5 h-2.5 rounded-full shrink-0" style={{ background: SOV_COLORS[i % SOV_COLORS.length] }} />
                  <span className="text-sm text-gray-700 flex-1 truncate" title={item.entity_name}>{item.entity_name}</span>
                  <span className="text-sm font-semibold text-gray-900">{item.pct}%</span>
                  <span className="text-xs text-gray-400">{item.mention_count.toLocaleString()}</span>
                </div>
              ))}
            </div>
          </div>
        ) : (
          <p className="text-sm text-gray-400 text-center py-6">Sin datos en el período seleccionado</p>
        )}
      </div>

      {/* Fila inferior: bots por plataforma + top entidades */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        <div className="card">
          <h2 className="font-semibold text-gray-800 mb-1">% Bots por plataforma</h2>
          <p className="text-xs text-gray-400 mb-3">Clasificación ML — cuentas analizadas</p>
          {(data?.bots_by_platform?.length ?? 0) > 0 ? (
            <ReactECharts option={botPlatformOption} style={{ height: 220 }}
              onEvents={{
                click: (params) => setDrawer({
                  title: `Bots · ${params.data?.name}`,
                  params: { min_bot_score: 0.7, platform: params.data?.code },
                }),
              }}
            />
          ) : (
            <div className="text-center text-gray-400 py-10 text-sm">
              Sin datos aún — el clasificador corre cada 6h
            </div>
          )}
        </div>
        <div className="card xl:col-span-2">
          <h2 className="font-semibold text-gray-800 mb-4">Top 5 entidades — menciones negativas (últimos 7 días)</h2>
          <ReactECharts option={topEntitiesOption} style={{ height: 220 }}
            onEvents={{
              click: (params) => {
                const entity = data?.top_entities?.[params.dataIndex]
                if (!entity) return
                setDrawer({
                  title: `Menciones negativas · ${entity.name}`,
                  params: { sentiment: 'negative', entity_id: entity.entity_id },
                })
              },
            }}
          />
        </div>
      </div>

      {/* Drawer de detalle */}
      {drawer && (
        <>
          <div className="fixed inset-0 bg-black/30 z-40" onClick={() => setDrawer(null)} />
          <div className="fixed right-0 top-0 h-full w-full max-w-md bg-white shadow-2xl z-50 flex flex-col">
            <div className="flex items-center justify-between px-5 py-4 border-b border-gray-200">
              <h3 className="font-semibold text-gray-800 text-base">{drawer.title}</h3>
              <button onClick={() => setDrawer(null)}
                className="text-gray-400 hover:text-gray-700 text-2xl leading-none">&times;</button>
            </div>
            <div className="flex-1 overflow-y-auto">
              {drawerFetching && (
                <p className="text-center text-gray-400 text-sm py-12">Cargando...</p>
              )}
              {!drawerFetching && drawerError && (
                <p className="text-center text-red-400 text-sm py-12">Error al cargar menciones</p>
              )}
              {!drawerFetching && !drawerError && drawerData && (drawerData.mentions?.length ?? 0) === 0 && (
                <p className="text-center text-gray-400 text-sm py-12">Sin resultados</p>
              )}
              {!drawerFetching && drawerData?.mentions?.map(m => <MentionRow key={m.id} m={m} />)}
            </div>
            <div className="px-5 py-3 border-t border-gray-100 text-center">
              <a href={`/mentions?${new URLSearchParams(
                  Object.fromEntries(Object.entries(drawer.params).filter(([,v]) => v != null))
                )}`}
                className="text-sm text-blue-600 hover:underline">
                Ver todas en Menciones →
              </a>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
