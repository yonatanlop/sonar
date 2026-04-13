import { useState } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { FileText, Download, Plus, Loader } from 'lucide-react'
import { format } from 'date-fns'
import { es } from 'date-fns/locale'
import toast from 'react-hot-toast'
import client from '../api/client'

const fetchReports  = ()  => client.get('/reports').then(r => r.data)
const fetchEntities = ()  => client.get('/entities').then(r => r.data)

const TYPE_LABEL = {
  entity:  'Por entidad',
  country: 'Por país',
  bots:    'Por bots',
  alerts:  'Por alertas',
  campaign:'Por campaña',
}

export default function Reports() {
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState({
    name: '', report_type: 'entity', entity_id: '',
    country_code: '', date_from: '', date_to: '',
  })

  const { data: reports  = [], refetch } = useQuery({ queryKey: ['reports'],  queryFn: fetchReports  })
  const { data: entities = [] }          = useQuery({ queryKey: ['entities'], queryFn: fetchEntities })

  const generate = useMutation({
    mutationFn: (body) => client.post('/reports', body),
    onSuccess: () => {
      toast.success('Reporte generado exitosamente')
      refetch()
      setShowForm(false)
    },
  })

  const download = async (report) => {
    try {
      const res = await client.get(`/reports/${report.id}/download`, { responseType: 'blob' })
      const url = URL.createObjectURL(res.data)
      const a   = document.createElement('a')
      a.href = url
      a.download = `${report.name}.pdf`
      a.click()
      URL.revokeObjectURL(url)
    } catch {
      toast.error('Error al descargar el reporte')
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Reportes</h1>
          <p className="text-gray-500 text-sm mt-0.5">Generación y descarga de reportes PDF</p>
        </div>
        <button onClick={() => setShowForm(!showForm)} className="btn-primary">
          <Plus className="w-4 h-4" /> Nuevo reporte
        </button>
      </div>

      {/* Formulario */}
      {showForm && (
        <div className="card border-primary-200 border-2">
          <h2 className="font-semibold mb-4">Generar nuevo reporte</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="label">Nombre del reporte *</label>
              <input className="input" placeholder="Ej: Reporte marzo 2026"
                value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} />
            </div>
            <div>
              <label className="label">Tipo *</label>
              <select className="input" value={form.report_type}
                onChange={e => setForm(f => ({ ...f, report_type: e.target.value }))}>
                {Object.entries(TYPE_LABEL).map(([k, v]) => (
                  <option key={k} value={k}>{v}</option>
                ))}
              </select>
            </div>
            {form.report_type === 'entity' && (
              <div>
                <label className="label">Entidad</label>
                <select className="input" value={form.entity_id}
                  onChange={e => setForm(f => ({ ...f, entity_id: e.target.value }))}>
                  <option value="">Seleccionar entidad</option>
                  {entities.map(e => <option key={e.id} value={e.id}>{e.name}</option>)}
                </select>
              </div>
            )}
            {form.report_type === 'country' && (
              <div>
                <label className="label">País (código)</label>
                <input className="input" placeholder="CO, MX, US..."
                  value={form.country_code}
                  onChange={e => setForm(f => ({ ...f, country_code: e.target.value }))} />
              </div>
            )}
            <div>
              <label className="label">Fecha desde *</label>
              <input className="input" type="date" value={form.date_from}
                onChange={e => setForm(f => ({ ...f, date_from: e.target.value }))} />
            </div>
            <div>
              <label className="label">Fecha hasta *</label>
              <input className="input" type="date" value={form.date_to}
                onChange={e => setForm(f => ({ ...f, date_to: e.target.value }))} />
            </div>
          </div>
          <div className="flex gap-2 mt-4">
            <button
              onClick={() => generate.mutate({
                  ...form,
                  entity_id:    form.entity_id    || null,
                  country_code: form.country_code || null,
                })}
              disabled={generate.isPending || !form.name || !form.date_from || !form.date_to}
              className="btn-primary"
            >
              {generate.isPending
                ? <><Loader className="w-4 h-4 animate-spin" /> Generando...</>
                : <><FileText className="w-4 h-4" /> Generar PDF</>}
            </button>
            <button onClick={() => setShowForm(false)} className="btn-secondary">Cancelar</button>
          </div>
        </div>
      )}

      {/* Listado de reportes */}
      <div className="space-y-2">
        {reports.length === 0 && (
          <div className="card text-center text-gray-400 py-12">
            <FileText className="w-8 h-8 mx-auto mb-2 opacity-30" />
            No hay reportes generados aún
          </div>
        )}
        {reports.map(report => (
          <div key={report.id} className="card py-4 flex items-center gap-4">
            <div className="bg-primary-50 rounded-lg p-2.5 shrink-0">
              <FileText className="w-5 h-5 text-primary-600" />
            </div>
            <div className="flex-1 min-w-0">
              <p className="font-medium text-gray-900 truncate">{report.name}</p>
              <p className="text-xs text-gray-400">
                {TYPE_LABEL[report.report_type]} ·{' '}
                {format(new Date(report.date_from), "d MMM", { locale: es })} -{' '}
                {format(new Date(report.date_to), "d MMM yyyy", { locale: es })} ·{' '}
                Generado por {report.created_by_name}
              </p>
            </div>
            <button onClick={() => download(report)} className="btn-secondary text-sm shrink-0">
              <Download className="w-4 h-4" /> Descargar
            </button>
          </div>
        ))}
      </div>
    </div>
  )
}
