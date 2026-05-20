import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { MapPin } from 'lucide-react'
import client from '../api/client'

const fetchGeo      = (days, entityId) =>
  client.get('/dashboard/geo-distribution', { params: { days, ...(entityId ? { entity_id: entityId } : {}) } }).then(r => r.data)
const fetchEntities = () => client.get('/entities').then(r => r.data)

const SENTIMENT_COLOR = (avg) => {
  if (avg == null) return '#9ca3af'
  if (avg < -0.2) return '#ef4444'
  if (avg > 0.2)  return '#22c55e'
  return '#9ca3af'
}

export default function GeoMap() {
  const [days, setDays]         = useState(7)
  const [entityId, setEntityId] = useState('')

  const { data: geoData, isLoading } = useQuery({
    queryKey: ['geo', days, entityId],
    queryFn:  () => fetchGeo(days, entityId || null),
  })
  const { data: entities = [] } = useQuery({ queryKey: ['entities'], queryFn: fetchEntities })

  const items = geoData?.items ?? []

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Mapa Geográfico</h1>
        <p className="text-gray-500 text-sm mt-0.5">Distribución de menciones por país de origen del autor</p>
      </div>

      {/* Filtros */}
      <div className="card py-3">
        <div className="flex flex-wrap gap-3">
          <select className="input w-auto" value={entityId} onChange={e => setEntityId(e.target.value)}>
            <option value="">Todas las entidades</option>
            {entities.map(e => <option key={e.id} value={e.id}>{e.name}</option>)}
          </select>
          <select className="input w-auto" value={days} onChange={e => setDays(Number(e.target.value))}>
            <option value={7}>Últimos 7 días</option>
            <option value={14}>Últimos 14 días</option>
            <option value={30}>Últimos 30 días</option>
          </select>
        </div>
      </div>

      {isLoading ? (
        <div className="text-center text-gray-400 py-12">Cargando datos geográficos...</div>
      ) : items.length === 0 ? (
        <div className="card text-center py-16 text-gray-400">
          <MapPin className="w-10 h-10 mx-auto mb-3 opacity-30" />
          <p className="font-medium">Sin datos de ubicación aún</p>
          <p className="text-sm mt-1">
            La geocodificación corre automáticamente cada 2h.<br />
            Para forzarla: <code className="bg-gray-100 px-1 rounded text-xs">docker compose exec worker python -c "from app.workers.tasks.analytics import geocode_mentions; geocode_mentions()"</code>
          </p>
        </div>
      ) : (
        <>
          {/* KPI */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            <div className="card text-center">
              <p className="text-2xl font-bold text-gray-900">{geoData.total?.toLocaleString()}</p>
              <p className="text-xs text-gray-500 mt-0.5">Menciones con ubicación</p>
            </div>
            <div className="card text-center">
              <p className="text-2xl font-bold text-gray-900">{items.length}</p>
              <p className="text-xs text-gray-500 mt-0.5">Países detectados</p>
            </div>
            <div className="card text-center">
              <p className="text-2xl font-bold text-primary-700">{items[0]?.country_name}</p>
              <p className="text-xs text-gray-500 mt-0.5">País principal</p>
            </div>
            <div className="card text-center">
              <p className="text-2xl font-bold text-gray-900">{items[0]?.pct}%</p>
              <p className="text-xs text-gray-500 mt-0.5">Concentración #1</p>
            </div>
          </div>

          {/* Tabla de países */}
          <div className="card overflow-x-auto">
            <h2 className="font-semibold text-gray-800 mb-4">Distribución por país</h2>
            <table className="min-w-[500px] w-full text-sm">
              <thead>
                <tr className="text-xs text-gray-500 border-b">
                  <th className="text-left pb-2 font-medium">#</th>
                  <th className="text-left pb-2 font-medium">País</th>
                  <th className="text-right pb-2 font-medium">Menciones</th>
                  <th className="text-right pb-2 font-medium">% del total</th>
                  <th className="text-center pb-2 font-medium">Sentimiento</th>
                  <th className="pb-2"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {items.map((item, i) => {
                  const flag = item.country_code?.length === 2
                    ? String.fromCodePoint(...[...item.country_code.toUpperCase()].map(c => 127397 + c.charCodeAt(0)))
                    : '🌐'
                  const sentLabel = item.avg_sentiment == null ? '—'
                    : item.avg_sentiment < -0.2 ? 'Negativo'
                    : item.avg_sentiment > 0.2  ? 'Positivo'
                    : 'Neutral'
                  const sentCls = item.avg_sentiment == null ? 'text-gray-400'
                    : item.avg_sentiment < -0.2 ? 'text-red-600'
                    : item.avg_sentiment > 0.2  ? 'text-green-600'
                    : 'text-gray-500'
                  return (
                    <tr key={item.country_code} className="hover:bg-gray-50">
                      <td className="py-2.5 text-gray-400 w-8">{i + 1}</td>
                      <td className="py-2.5 font-medium text-gray-800">
                        <span className="mr-2">{flag}</span>{item.country_name}
                        <span className="text-xs text-gray-400 ml-1">({item.country_code})</span>
                      </td>
                      <td className="py-2.5 text-right text-gray-700">{item.mention_count.toLocaleString()}</td>
                      <td className="py-2.5 text-right text-gray-700 w-20">{item.pct}%</td>
                      <td className={`py-2.5 text-center text-xs font-medium ${sentCls}`}>{sentLabel}</td>
                      <td className="py-2.5 w-32">
                        <div className="bg-gray-100 rounded-full h-1.5 overflow-hidden">
                          <div
                            className="h-full rounded-full"
                            style={{ width: `${item.pct}%`, background: SENTIMENT_COLOR(item.avg_sentiment) }}
                          />
                        </div>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  )
}
