import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { format } from 'date-fns'
import { es } from 'date-fns/locale'
import { ScrollText, ChevronLeft, ChevronRight } from 'lucide-react'
import client from '../api/client'

const ACTION_LABELS = {
  login:                'Inicio de sesión',
  logout:               'Cierre de sesión',
  user_created:         'Usuario creado',
  user_updated:         'Usuario editado',
  user_deactivated:     'Usuario desactivado',
  password_changed:     'Contraseña cambiada',
  entity_created:       'Entidad creada',
  entity_updated:       'Entidad editada',
  alias_added:          'Alias agregado',
  alias_deleted:        'Alias eliminado',
  keyword_added:        'Keyword agregada',
  keyword_deleted:      'Keyword eliminada',
  alert_acknowledged:   'Alerta reconocida',
  rule_created:         'Regla creada',
  rule_deleted:         'Regla eliminada',
  rule_toggled:         'Regla activada/desactivada',
  report_generated:     'Reporte generado',
  report_downloaded:    'Reporte descargado',
  yt_channel_added:     'Canal YouTube agregado',
  yt_channel_deleted:   'Canal YouTube eliminado',
  yt_videos_saved:      'Videos YouTube guardados',
  twitter_feed_added:   'Feed Twitter agregado',
  twitter_feed_deleted: 'Feed Twitter eliminado',
}

const MODULES = {
  users:            'Usuarios',
  entities:         'Entidades',
  alerts:           'Alertas',
  alert_rules:      'Reglas de alerta',
  reports:          'Reportes',
  youtube_channels: 'YouTube Explorer',
  twitter_feeds:    'Twitter Explorer',
}

const ACTION_BADGE = {
  login:                'bg-blue-100 text-blue-700',
  logout:               'bg-gray-100 text-gray-600',
  user_created:         'bg-green-100 text-green-700',
  user_updated:         'bg-yellow-100 text-yellow-700',
  user_deactivated:     'bg-red-100 text-red-700',
  password_changed:     'bg-purple-100 text-purple-700',
  entity_created:       'bg-green-100 text-green-700',
  entity_updated:       'bg-yellow-100 text-yellow-700',
  alias_added:          'bg-green-100 text-green-700',
  alias_deleted:        'bg-red-100 text-red-700',
  keyword_added:        'bg-green-100 text-green-700',
  keyword_deleted:      'bg-red-100 text-red-700',
  alert_acknowledged:   'bg-blue-100 text-blue-700',
  rule_created:         'bg-green-100 text-green-700',
  rule_deleted:         'bg-red-100 text-red-700',
  rule_toggled:         'bg-yellow-100 text-yellow-700',
  report_generated:     'bg-green-100 text-green-700',
  report_downloaded:    'bg-blue-100 text-blue-700',
  yt_channel_added:     'bg-green-100 text-green-700',
  yt_channel_deleted:   'bg-red-100 text-red-700',
  yt_videos_saved:      'bg-blue-100 text-blue-700',
  twitter_feed_added:   'bg-green-100 text-green-700',
  twitter_feed_deleted: 'bg-red-100 text-red-700',
}

const ALL_ACTIONS = Object.keys(ACTION_LABELS)

function formatDetails(details) {
  if (!details) return '—'
  return Object.entries(details)
    .map(([k, v]) => `${k}: ${v}`)
    .join(' · ')
}

export default function Audit() {
  const [page, setPage]          = useState(1)
  const [userId, setUserId]      = useState('')
  const [action, setAction]      = useState('')
  const [module, setModule]      = useState('')
  const [fromDate, setFromDate]  = useState('')
  const [toDate, setToDate]      = useState('')

  const params = {
    page,
    ...(userId   ? { user_id:      userId }   : {}),
    ...(action   ? { action }                 : {}),
    ...(module   ? { target_table: module }   : {}),
    ...(fromDate ? { from_date:    fromDate } : {}),
    ...(toDate   ? { to_date:      toDate }   : {}),
  }

  const { data, isLoading } = useQuery({
    queryKey: ['audit', params],
    queryFn:  () => client.get('/audit', { params }).then(r => r.data),
  })

  const { data: auditUsers } = useQuery({
    queryKey: ['audit-users'],
    queryFn:  () => client.get('/audit/users').then(r => r.data),
  })

  const handleFilter = () => setPage(1)

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <ScrollText className="w-5 h-5 text-primary-600" />
        <h1 className="text-xl font-bold text-gray-900">Auditoría del sistema</h1>
      </div>

      {/* Filtros */}
      <div className="card p-4 grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3">
        <div>
          <label className="label">Usuario</label>
          <select
            className="input"
            value={userId}
            onChange={e => { setUserId(e.target.value); handleFilter() }}
          >
            <option value="">Todos</option>
            {(auditUsers || []).map(u => (
              <option key={u.id} value={u.id}>{u.full_name}</option>
            ))}
          </select>
        </div>

        <div>
          <label className="label">Acción</label>
          <select
            className="input"
            value={action}
            onChange={e => { setAction(e.target.value); handleFilter() }}
          >
            <option value="">Todas</option>
            {ALL_ACTIONS.map(a => (
              <option key={a} value={a}>{ACTION_LABELS[a]}</option>
            ))}
          </select>
        </div>

        <div>
          <label className="label">Módulo</label>
          <select
            className="input"
            value={module}
            onChange={e => { setModule(e.target.value); handleFilter() }}
          >
            <option value="">Todos</option>
            {Object.entries(MODULES).map(([k, v]) => (
              <option key={k} value={k}>{v}</option>
            ))}
          </select>
        </div>

        <div>
          <label className="label">Desde</label>
          <input
            type="date"
            className="input"
            value={fromDate}
            onChange={e => { setFromDate(e.target.value); handleFilter() }}
          />
        </div>

        <div>
          <label className="label">Hasta</label>
          <input
            type="date"
            className="input"
            value={toDate}
            onChange={e => { setToDate(e.target.value); handleFilter() }}
          />
        </div>
      </div>

      {/* Tabla */}
      <div className="card overflow-hidden">
        {isLoading ? (
          <div className="p-8 text-center text-gray-500">Cargando...</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 border-b border-gray-200">
                <tr>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider">Fecha</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider">Usuario</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider">Acción</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider">Módulo</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider">Detalle</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider">IP</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {(data?.items || []).map(log => (
                  <tr key={log.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3 whitespace-nowrap text-gray-500">
                      {format(new Date(log.created_at), 'dd MMM yyyy HH:mm', { locale: es })}
                    </td>
                    <td className="px-4 py-3">
                      <div className="font-medium text-gray-900">{log.full_name}</div>
                      <div className="text-gray-400 text-xs">{log.username}</div>
                    </td>
                    <td className="px-4 py-3">
                      <span className={`badge ${ACTION_BADGE[log.action] || 'bg-gray-100 text-gray-600'}`}>
                        {log.action_label}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-gray-600">{log.module_label}</td>
                    <td className="px-4 py-3 text-gray-500 max-w-xs truncate">
                      {formatDetails(log.details)}
                    </td>
                    <td className="px-4 py-3 text-gray-400 text-xs whitespace-nowrap">
                      {log.ip_address || '—'}
                    </td>
                  </tr>
                ))}
                {(data?.items || []).length === 0 && (
                  <tr>
                    <td colSpan={6} className="px-4 py-8 text-center text-gray-400">
                      No hay registros de auditoría
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}

        {/* Paginación */}
        {data && data.pages > 1 && (
          <div className="px-4 py-3 border-t border-gray-200 flex items-center justify-between">
            <span className="text-sm text-gray-500">
              {data.total} registros · página {data.page} de {data.pages}
            </span>
            <div className="flex gap-2">
              <button
                className="btn-secondary px-3 py-1.5 text-sm flex items-center gap-1 disabled:opacity-40"
                onClick={() => setPage(p => p - 1)}
                disabled={page === 1}
              >
                <ChevronLeft className="w-4 h-4" /> Anterior
              </button>
              <button
                className="btn-secondary px-3 py-1.5 text-sm flex items-center gap-1 disabled:opacity-40"
                onClick={() => setPage(p => p + 1)}
                disabled={page === data.pages}
              >
                Siguiente <ChevronRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
