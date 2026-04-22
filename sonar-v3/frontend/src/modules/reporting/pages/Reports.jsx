import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { FileText, Download, Plus } from 'lucide-react'
import { format } from 'date-fns'
import { es } from 'date-fns/locale'
import toast from 'react-hot-toast'
import client from '../../../shared/api/client'
import { useAuthStore } from '../../../shared/store/authStore'

const fetchReports  = () => client.get('/reports').then(r => r.data)
const fetchEntities = () => client.get('/entities').then(r => r.data)

const REPORT_TYPES = ['entity','country','bots','alerts','campaign']

export default function Reports() {
  const qc = useQueryClient()
  const isAnalyst = useAuthStore(s => s.isAnalyst())
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState({
    name: '', report_type: 'entity', entity_id: '',
    date_from: '', date_to: '',
  })
  const set = (k, v) => setForm(f => ({ ...f, [k]: v }))

  const { data: reports  = [], isLoading } = useQuery({ queryKey: ['reports'],  queryFn: fetchReports })
  const { data: entities = [] }            = useQuery({ queryKey: ['entities'], queryFn: fetchEntities })

  const generate = useMutation({
    mutationFn: (body) => client.post('/reports', body),
    onSuccess: () => {
      toast.success('Reporte en generación — se actualizará en breve')
      qc.invalidateQueries({ queryKey: ['reports'] })
      setShowForm(false)
    },
    onError: (e) => toast.error(e?.response?.data?.detail ?? 'Error'),
  })

  if (isLoading) return <div className="text-center text-gray-400 py-12">Cargando...</div>

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Reportes</h1>
        {isAnalyst && !showForm && (
          <button className="btn-primary" onClick={() => setShowForm(true)}>
            <Plus className="w-4 h-4" /> Generar reporte
          </button>
        )}
      </div>

      {showForm && (
        <form onSubmit={e => { e.preventDefault(); generate.mutate(form) }}
          className="card space-y-4">
          <h2 className="font-semibold text-gray-800">Nuevo reporte</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="label">Nombre</label>
              <input className="input" value={form.name} onChange={e => set('name', e.target.value)} required />
            </div>
            <div>
              <label className="label">Tipo</label>
              <select className="input" value={form.report_type} onChange={e => set('report_type', e.target.value)}>
                {REPORT_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
              </select>
            </div>
            {form.report_type === 'entity' && (
              <div>
                <label className="label">Entidad</label>
                <select className="input" value={form.entity_id} onChange={e => set('entity_id', e.target.value)} required>
                  <option value="">Selecciona...</option>
                  {entities.map(e => <option key={e.id} value={e.id}>{e.name}</option>)}
                </select>
              </div>
            )}
            <div>
              <label className="label">Desde</label>
              <input className="input" type="date" value={form.date_from} onChange={e => set('date_from', e.target.value)} required />
            </div>
            <div>
              <label className="label">Hasta</label>
              <input className="input" type="date" value={form.date_to} onChange={e => set('date_to', e.target.value)} required />
            </div>
          </div>
          <div className="flex gap-2">
            <button type="submit" className="btn-primary" disabled={generate.isPending}>
              {generate.isPending ? 'Generando...' : 'Generar PDF'}
            </button>
            <button type="button" className="btn-secondary" onClick={() => setShowForm(false)}>
              Cancelar
            </button>
          </div>
        </form>
      )}

      <div className="space-y-3">
        {reports.map(r => (
          <div key={r.id} className="card p-4 flex items-center gap-4">
            <FileText className="w-8 h-8 text-primary-400 shrink-0" />
            <div className="flex-1 min-w-0">
              <p className="font-medium text-gray-900 truncate">{r.name}</p>
              <p className="text-xs text-gray-400">
                {r.report_type} · {format(new Date(r.created_at), "d MMM yyyy", { locale: es })}
              </p>
            </div>
            {r.file_path ? (
              <a href={`/api/v3/reports/${r.id}/download`}
                className="btn-secondary text-xs py-1.5 px-3 shrink-0">
                <Download className="w-3.5 h-3.5" /> Descargar
              </a>
            ) : (
              <span className="badge badge-neutral text-xs shrink-0">Generando…</span>
            )}
          </div>
        ))}
        {reports.length === 0 && (
          <div className="text-center text-gray-400 py-12">No hay reportes generados</div>
        )}
      </div>
    </div>
  )
}
