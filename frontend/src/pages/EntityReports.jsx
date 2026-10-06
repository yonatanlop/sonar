/**
 * Informe de actividad de entidades.
 * - Días, meses y años con más menciones (filtrable por fecha).
 * - Eventos del día registrados por el equipo, para explicar los picos.
 * - Keywords y cuentas que más publican, con referencia a Rizoma cuando la cuenta ya está registrada.
 */
import { useMemo, useState } from 'react'
import ReactECharts from 'echarts-for-react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { BarChart3, CalendarPlus, Trash2, ShieldAlert, Activity, Flame, Users } from 'lucide-react'
import toast from 'react-hot-toast'
import client from '../api/client'
import ModuleHelp from '../components/ModuleHelp'

const SERIES = '#2a78d6'          // ranura 1 de la paleta categórica (única serie = un solo color)
const TEXT_SECONDARY = '#52514e'
const DEFAULT_NAMES = ['IDMJI Oficial', 'María Luisa Piraquive']
const PRESETS = [{ label: '30 días', days: 30 }, { label: '90 días', days: 90 }, { label: '1 año', days: 365 }]

const fmtDay = (iso) => {
  if (!iso) return '—'
  const [y, m, d] = iso.split('-')
  return `${d}/${m}/${y}`
}
const fmtMonth = (ym) => {
  const [y, m] = ym.split('-')
  return new Date(Number(y), Number(m) - 1, 1).toLocaleDateString('es', { month: 'long', year: 'numeric' })
}
const isoDaysAgo = (days) => {
  const d = new Date(Date.now() - (days - 1) * 86400000)
  return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10)
}
const todayIso = () => isoDaysAgo(1)

const fetchEntities = () => client.get('/entities', { params: { active_only: false } }).then(r => Array.isArray(r.data) ? r.data : (r.data.items || []))

export default function EntityReports() {
  const qc = useQueryClient()
  const [selected, setSelected] = useState(null)   // null = aún no inicializado con las por defecto
  const [dateFrom, setDateFrom] = useState(isoDaysAgo(90))
  const [dateTo, setDateTo] = useState(todayIso())
  const [eventForm, setEventForm] = useState({ entity_id: '', event_date: '', title: '', description: '' })

  const { data: entities = [] } = useQuery({ queryKey: ['entities-list'], queryFn: fetchEntities })
  const selectable = useMemo(
    () => entities.filter(e => !e.name?.startsWith('[') && e.name !== 'Búsqueda Twitter Global'),
    [entities],
  )

  const selectedIds = useMemo(() => {
    if (selected !== null) return selected
    return selectable.filter(e => DEFAULT_NAMES.includes(e.name)).map(e => e.id)
  }, [selected, selectable])

  const hasSelection = selectedIds.length > 0
  const { data: report, isLoading, isError } = useQuery({
    queryKey: ['entity-report', selectedIds.join(','), dateFrom, dateTo],
    queryFn: () => client.get('/entity-reports', {
      params: { entity_ids: selectedIds.join(','), date_from: dateFrom, date_to: dateTo },
    }).then(r => r.data),
    enabled: hasSelection && !!dateFrom && !!dateTo,
  })

  const invalidate = () => qc.invalidateQueries({ queryKey: ['entity-report'] })
  const addEvent = useMutation({
    mutationFn: (body) => client.post('/entity-reports/events', body),
    onSuccess: () => {
      toast.success('Evento registrado')
      setEventForm(f => ({ ...f, title: '', description: '' }))
      invalidate()
    },
    onError: (e) => toast.error(e.response?.data?.detail || 'No se pudo registrar el evento'),
  })
  const removeEvent = useMutation({
    mutationFn: (id) => client.delete(`/entity-reports/events/${id}`),
    onSuccess: () => { toast.success('Evento eliminado'); invalidate() },
    onError: (e) => toast.error(e.response?.data?.detail || 'No se pudo eliminar el evento'),
  })

  function toggleEntity(id) {
    const base = selected !== null ? selected : selectedIds
    setSelected(base.includes(id) ? base.filter(x => x !== id) : [...base, id])
  }
  function applyPreset(days) {
    setDateFrom(isoDaysAgo(days))
    setDateTo(todayIso())
  }
  function prefillEvent(date) {
    setEventForm(f => ({ ...f, event_date: date, entity_id: f.entity_id || selectedIds[0] || '' }))
    document.getElementById('evento-del-dia')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }
  function submitEvent(e) {
    e.preventDefault()
    if (!eventForm.entity_id || !eventForm.event_date || !eventForm.title.trim()) {
      toast.error('Entidad, fecha y título son obligatorios')
      return
    }
    addEvent.mutate({
      entity_id: eventForm.entity_id,
      event_date: eventForm.event_date,
      title: eventForm.title.trim(),
      description: eventForm.description.trim() || null,
    })
  }

  const eventDates = useMemo(() => new Set((report?.events || []).map(ev => ev.date)), [report])

  const timelineOption = useMemo(() => {
    if (!report) return null
    const counts = Object.fromEntries(report.daily.map(p => [p.date, p.count]))
    const days = []
    const cursor = new Date(report.date_from + 'T12:00:00')
    const end = new Date(report.date_to + 'T12:00:00')
    while (cursor <= end) {
      days.push(new Date(cursor.getTime() - cursor.getTimezoneOffset() * 60000).toISOString().slice(0, 10))
      cursor.setDate(cursor.getDate() + 1)
    }
    const markers = days
      .filter(d => eventDates.has(d))
      .map(d => ({ coord: [d, counts[d] || 0], value: 'E', itemStyle: { color: TEXT_SECONDARY } }))
    return {
      grid: { left: 48, right: 16, top: 24, bottom: 56 },
      tooltip: {
        trigger: 'axis',
        formatter: (params) => {
          const p = params[0]
          const evs = (report.events || []).filter(ev => ev.date === p.name)
          const lines = [`<b>${fmtDay(p.name)}</b>: ${p.value} menciones`]
          evs.forEach(ev => lines.push(`● ${ev.title}`))
          return lines.join('<br/>')
        },
      },
      xAxis: { type: 'category', data: days, axisLabel: { color: TEXT_SECONDARY, formatter: v => fmtDay(v).slice(0, 5), hideOverlap: true } },
      yAxis: { type: 'value', name: 'Menciones', nameTextStyle: { color: TEXT_SECONDARY }, axisLabel: { color: TEXT_SECONDARY }, splitLine: { lineStyle: { opacity: 0.2 } } },
      dataZoom: [{ type: 'inside' }, { type: 'slider', height: 16, bottom: 8 }],
      series: [{
        type: 'bar', data: days.map(d => counts[d] || 0), itemStyle: { color: SERIES, borderRadius: [4, 4, 0, 0] },
        barMaxWidth: 14,
        markPoint: { data: markers, symbol: 'pin', symbolSize: 26, label: { formatter: 'E', color: '#fff', fontSize: 10 } },
      }],
    }
  }, [report, eventDates])

  const monthOption = useMemo(() => {
    if (!report) return null
    return {
      grid: { left: 48, right: 16, top: 16, bottom: 36 },
      tooltip: { trigger: 'axis', formatter: p => `<b>${fmtMonth(p[0].name)}</b>: ${p[0].value} menciones` },
      xAxis: { type: 'category', data: report.by_month.map(m => m.month), axisLabel: { color: TEXT_SECONDARY, formatter: v => v.slice(2) } },
      yAxis: { type: 'value', axisLabel: { color: TEXT_SECONDARY }, splitLine: { lineStyle: { opacity: 0.2 } } },
      series: [{ type: 'bar', data: report.by_month.map(m => m.count), itemStyle: { color: SERIES, borderRadius: [4, 4, 0, 0] }, barMaxWidth: 28 }],
    }
  }, [report])

  const keywordOption = useMemo(() => {
    if (!report) return null
    const rows = [...report.keywords].reverse()
    return {
      grid: { left: 8, right: 48, top: 8, bottom: 8, containLabel: true },
      tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' }, formatter: p => `<b>${p[0].name}</b>: ${p[0].value} menciones` },
      xAxis: { type: 'value', axisLabel: { color: TEXT_SECONDARY }, splitLine: { lineStyle: { opacity: 0.2 } } },
      yAxis: { type: 'category', data: rows.map(r => r.keyword), axisLabel: { color: TEXT_SECONDARY, width: 200, overflow: 'truncate' } },
      series: [{ type: 'bar', data: rows.map(r => r.count), itemStyle: { color: SERIES, borderRadius: [0, 4, 4, 0] }, barMaxWidth: 16, label: { show: true, position: 'right', color: TEXT_SECONDARY } }],
    }
  }, [report])

  const peak = report?.peaks?.[0]

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-2">
          <BarChart3 className="w-6 h-6 text-primary-600" />
          <div>
            <h1 className="text-xl font-bold text-gray-900">Informe de actividad <ModuleHelp id="entity-activity" /></h1>
            <p className="text-sm text-gray-500">Cuándo se activan las menciones, qué las impulsa y quién las publica</p>
          </div>
        </div>
      </div>

      <div className="card space-y-3">
        <div className="flex flex-wrap gap-2">
          {selectable.map(e => {
            const on = selectedIds.includes(e.id)
            return (
              <button
                key={e.id}
                onClick={() => toggleEntity(e.id)}
                className={`px-3 py-1.5 rounded-full text-sm border ${on ? 'bg-primary-600 text-white border-primary-600' : 'bg-white text-gray-600 border-gray-300'}`}
              >
                {e.name}
              </button>
            )
          })}
        </div>
        <div className="flex flex-wrap items-end gap-3">
          <div>
            <label className="label">Desde</label>
            <input type="date" className="input w-auto" value={dateFrom} onChange={e => setDateFrom(e.target.value)} />
          </div>
          <div>
            <label className="label">Hasta</label>
            <input type="date" className="input w-auto" value={dateTo} onChange={e => setDateTo(e.target.value)} />
          </div>
          <div className="flex gap-2">
            {PRESETS.map(p => (
              <button key={p.days} onClick={() => applyPreset(p.days)} className="btn-secondary text-sm">{p.label}</button>
            ))}
          </div>
        </div>
      </div>

      {!hasSelection && <p className="text-sm text-gray-500">Selecciona al menos una entidad.</p>}
      {isError && <p className="text-sm text-red-600">No se pudo cargar el informe.</p>}
      {isLoading && hasSelection && <p className="text-sm text-gray-500">Calculando…</p>}

      {report && (
        <>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
            <KpiTile icon={Activity} label="Menciones en el rango" value={report.total.toLocaleString('es')} />
            <KpiTile icon={CalendarPlus} label="Días con actividad" value={report.active_days} />
            <KpiTile icon={Flame} label="Día con más menciones" value={peak ? `${fmtDay(peak.date)} · ${peak.count}` : '—'} />
            <KpiTile icon={Users} label="Eventos registrados" value={report.events.length} />
          </div>

          <section className="card">
            <h2 className="font-semibold text-gray-900 mb-1">Menciones por día</h2>
            <p className="text-xs text-gray-500 mb-2">La “E” marca los días con un evento registrado (ver abajo).</p>
            {timelineOption && <ReactECharts option={timelineOption} style={{ height: 280 }} />}
          </section>

          <div className="grid lg:grid-cols-2 gap-6">
            <section className="card">
              <h2 className="font-semibold text-gray-900 mb-2">Por mes</h2>
              {report.by_month.length ? <ReactECharts option={monthOption} style={{ height: 240 }} /> : <p className="text-sm text-gray-500">Sin menciones en el rango.</p>}
              <div className="flex flex-wrap gap-3 mt-3 text-sm text-gray-600">
                {report.by_year.map(y => <span key={y.year}><b className="text-gray-900">{y.year}</b>: {y.count.toLocaleString('es')}</span>)}
              </div>
            </section>

            <section className="card">
              <h2 className="font-semibold text-gray-900 mb-2">Días con más menciones</h2>
              {report.peaks.length === 0 ? <p className="text-sm text-gray-500">Sin datos.</p> : (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead className="text-left text-gray-500 text-xs uppercase">
                      <tr><th className="py-1">Fecha</th><th>Año</th><th>Mes</th><th>Día</th><th className="text-right">Menciones</th><th className="text-right"></th></tr>
                    </thead>
                    <tbody>
                      {report.peaks.map(p => {
                        const [y, m, d] = p.date.split('-')
                        return (
                          <tr key={p.date} className="border-t border-gray-100">
                            <td className="py-1.5 font-medium text-gray-900">{fmtDay(p.date)}</td>
                            <td>{y}</td>
                            <td>{fmtMonth(`${y}-${m}`)}</td>
                            <td>{Number(d)}</td>
                            <td className="text-right">{p.count}</td>
                            <td className="text-right">
                              <button onClick={() => prefillEvent(p.date)} className="text-primary-600 hover:underline text-xs">+ Evento</button>
                            </td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </section>
          </div>

          <section id="evento-del-dia" className="card">
            <h2 className="font-semibold text-gray-900 mb-1">Eventos del día</h2>
            <p className="text-xs text-gray-500 mb-3">Registra qué pasó ese día (una noticia, una declaración, una acción) para explicar el pico de menciones.</p>
            <form onSubmit={submitEvent} className="grid md:grid-cols-4 gap-3 items-end mb-4">
              <div>
                <label className="label">Entidad</label>
                <select className="input w-full" value={eventForm.entity_id} onChange={e => setEventForm(f => ({ ...f, entity_id: e.target.value }))}>
                  <option value="">—</option>
                  {selectable.filter(e => selectedIds.includes(e.id)).map(e => <option key={e.id} value={e.id}>{e.name}</option>)}
                </select>
              </div>
              <div>
                <label className="label">Fecha</label>
                <input type="date" className="input w-full" value={eventForm.event_date} onChange={e => setEventForm(f => ({ ...f, event_date: e.target.value }))} />
              </div>
              <div>
                <label className="label">Evento</label>
                <input className="input w-full" maxLength={200} value={eventForm.title} onChange={e => setEventForm(f => ({ ...f, title: e.target.value }))} placeholder="Ej.: Publicación de la declaración" />
              </div>
              <div>
                <label className="label">Detalle (opcional)</label>
                <input className="input w-full" value={eventForm.description} onChange={e => setEventForm(f => ({ ...f, description: e.target.value }))} />
              </div>
              <div className="md:col-span-4 flex justify-end">
                <button type="submit" disabled={addEvent.isPending} className="btn-primary">{addEvent.isPending ? 'Guardando…' : 'Registrar evento'}</button>
              </div>
            </form>
            {report.events.length === 0 ? <p className="text-sm text-gray-500">No hay eventos en el rango.</p> : (
              <ul className="divide-y divide-gray-100">
                {report.events.map(ev => (
                  <li key={ev.id} className="py-2 flex items-start justify-between gap-3">
                    <div>
                      <div className="text-sm"><b className="text-gray-900">{fmtDay(ev.date)}</b> · {ev.entity_name} · {ev.title}</div>
                      {ev.description && <div className="text-xs text-gray-500">{ev.description}</div>}
                      <div className="text-xs text-gray-400">Registrado por {ev.created_by}</div>
                    </div>
                    <button onClick={() => removeEvent.mutate(ev.id)} className="text-gray-400 hover:text-red-600" title="Eliminar evento">
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <div className="grid lg:grid-cols-2 gap-6">
            <section className="card">
              <h2 className="font-semibold text-gray-900 mb-2">Keywords más usadas</h2>
              <p className="text-xs text-gray-500 mb-2">Cuántas menciones del rango coincidieron con cada keyword (una mención puede coincidir con varias).</p>
              {report.keywords.length ? <ReactECharts option={keywordOption} style={{ height: Math.max(180, report.keywords.length * 26) }} /> : <p className="text-sm text-gray-500">Sin datos.</p>}
            </section>

            <section className="card">
              <h2 className="font-semibold text-gray-900 mb-2">Cuentas que más publican</h2>
              {report.accounts.length === 0 ? <p className="text-sm text-gray-500">Sin datos.</p> : (
                <div className="overflow-x-auto max-h-[420px] overflow-y-auto">
                  <table className="w-full text-sm">
                    <thead className="text-left text-gray-500 text-xs uppercase sticky top-0 bg-white">
                      <tr><th className="py-1">Cuenta</th><th>Red</th><th>Entidad</th><th className="text-right">Menciones</th><th>Rizoma</th></tr>
                    </thead>
                    <tbody>
                      {report.accounts.map((a, i) => (
                        <tr key={`${a.platform}-${a.author}-${i}`} className="border-t border-gray-100">
                          <td className="py-1.5 font-medium text-gray-900">@{a.author?.replace(/^@/, '')}</td>
                          <td className="capitalize">{a.platform}</td>
                          <td className="text-gray-600">{a.entity_name}</td>
                          <td className="text-right">{a.mentions}</td>
                          <td>
                            {a.rizoma ? (
                              <Link to="/rizoma" className="inline-flex items-center gap-1 badge bg-red-100 text-red-700">
                                <ShieldAlert className="w-3 h-3" /> {a.rizoma.case_name}{a.rizoma.account_removed ? ' · cerrada' : ''}
                              </Link>
                            ) : <span className="text-gray-400 text-xs">No registrada</span>}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </section>
          </div>
        </>
      )}
    </div>
  )
}

function KpiTile({ icon: Icon, label, value }) {
  return (
    <div className="card flex items-center gap-3">
      <Icon className="w-5 h-5 text-primary-600" />
      <div>
        <div className="text-xs text-gray-500">{label}</div>
        <div className="text-lg font-semibold text-gray-900">{value}</div>
      </div>
    </div>
  )
}
