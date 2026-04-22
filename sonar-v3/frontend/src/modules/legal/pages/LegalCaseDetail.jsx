import { useRef } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { format } from 'date-fns'
import { es } from 'date-fns/locale'
import { ArrowLeft, ArrowUpRight, Paperclip, MessageSquare } from 'lucide-react'
import toast from 'react-hot-toast'
import client from '../../../shared/api/client'
import { useAuthStore } from '../../../shared/store/authStore'

const fetchCase = (id) => client.get(`/legal/cases/${id}`).then(r => r.data)

const LEVEL_LABEL = { platform: 'Plataforma', mira_legal: 'Jurídico MIRA', church_legal: 'Jurídico Iglesia' }
const LEVEL_COLOR = { platform: 'badge-low', mira_legal: 'badge-medium', church_legal: 'badge-high' }
const STATUS_LABEL = { open: 'Abierto', in_review: 'En revisión', escalated: 'Escalado', resolved: 'Resuelto', closed: 'Cerrado' }

const EVENT_ICON = {
  created:   '🆕',
  escalated: '⬆️',
  updated:   '✏️',
  note:      '📝',
}

export default function LegalCaseDetail() {
  const { id } = useParams()
  const qc = useQueryClient()
  const isAnalyst = useAuthStore(s => s.isAnalyst())
  const fileRef = useRef()

  const { data: c, isLoading } = useQuery({
    queryKey: ['legal-case', id],
    queryFn: () => fetchCase(id),
  })

  const escalate = useMutation({
    mutationFn: () => client.post(`/legal/cases/${id}/escalate`),
    onSuccess: () => { toast.success('Caso escalado'); qc.invalidateQueries({ queryKey: ['legal-case', id] }) },
    onError: (e) => toast.error(e?.response?.data?.detail ?? 'Error'),
  })

  const addEvent = useMutation({
    mutationFn: (body) => client.post(`/legal/cases/${id}/events`, body),
    onSuccess: () => { toast.success('Evento añadido'); qc.invalidateQueries({ queryKey: ['legal-case', id] }) },
    onError: (e) => toast.error(e?.response?.data?.detail ?? 'Error'),
  })

  const uploadDoc = useMutation({
    mutationFn: async (file) => {
      const fd = new FormData()
      fd.append('file', file)
      return client.post(`/legal/cases/${id}/documents`, fd, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
    },
    onSuccess: () => { toast.success('Documento adjuntado'); qc.invalidateQueries({ queryKey: ['legal-case', id] }) },
    onError: (e) => toast.error(e?.response?.data?.detail ?? 'Error'),
  })

  const handleAddNote = () => {
    const desc = prompt('Descripción del evento:')
    if (!desc) return
    addEvent.mutate({ event_type: 'note', description: desc })
  }

  if (isLoading) return <div className="text-center text-gray-400 py-12">Cargando...</div>
  if (!c) return null

  const canEscalate = isAnalyst && ['platform','mira_legal'].includes(c.level) && c.status !== 'closed'

  return (
    <div className="space-y-6 max-w-3xl">
      <div className="flex items-center gap-3">
        <Link to="/legal" className="text-gray-400 hover:text-gray-600">
          <ArrowLeft className="w-5 h-5" />
        </Link>
        <h1 className="text-xl font-bold text-gray-900 flex-1">{c.title}</h1>
      </div>

      {/* Cabecera con badges y acciones */}
      <div className="card p-4 flex flex-wrap items-center gap-3">
        <span className={`badge ${LEVEL_COLOR[c.level]}`}>{LEVEL_LABEL[c.level]}</span>
        <span className={`badge badge-${c.status}`}>{STATUS_LABEL[c.status]}</span>
        <div className="flex-1" />
        {canEscalate && (
          <button className="btn-primary text-xs py-1.5 px-3" onClick={() => escalate.mutate()}
            disabled={escalate.isPending}>
            <ArrowUpRight className="w-3.5 h-3.5" />
            {escalate.isPending ? 'Escalando...' : 'Escalar nivel'}
          </button>
        )}
        {isAnalyst && (
          <>
            <button className="btn-secondary text-xs py-1.5 px-3" onClick={handleAddNote}>
              <MessageSquare className="w-3.5 h-3.5" /> Añadir nota
            </button>
            <button className="btn-secondary text-xs py-1.5 px-3"
              onClick={() => fileRef.current?.click()}>
              <Paperclip className="w-3.5 h-3.5" /> Adjuntar
            </button>
            <input ref={fileRef} type="file" className="hidden"
              onChange={e => { if (e.target.files[0]) uploadDoc.mutate(e.target.files[0]) }} />
          </>
        )}
      </div>

      {c.description && (
        <div className="card">
          <h2 className="font-semibold text-gray-800 mb-2">Descripción</h2>
          <p className="text-sm text-gray-700 leading-relaxed">{c.description}</p>
        </div>
      )}

      {/* Timeline de eventos */}
      <div className="card">
        <h2 className="font-semibold text-gray-800 mb-4">Historial</h2>
        <div className="relative">
          <div className="absolute left-4 top-0 bottom-0 w-px bg-gray-200" />
          <div className="space-y-4">
            {(c.events ?? []).map(e => (
              <div key={e.id} className="flex items-start gap-4 ml-0">
                <div className="relative z-10 w-8 h-8 rounded-full bg-white border-2 border-gray-200 flex items-center justify-center text-sm shrink-0">
                  {EVENT_ICON[e.event_type] ?? '📌'}
                </div>
                <div className="flex-1 pb-1">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-sm font-medium text-gray-900">{e.event_type}</span>
                    {e.from_level && e.to_level && (
                      <span className="text-xs text-gray-400">
                        {LEVEL_LABEL[e.from_level]} → {LEVEL_LABEL[e.to_level]}
                      </span>
                    )}
                    <span className="text-xs text-gray-400 ml-auto">
                      {format(new Date(e.created_at), "d MMM yyyy HH:mm", { locale: es })}
                    </span>
                  </div>
                  {e.description && (
                    <p className="text-sm text-gray-600 mt-0.5">{e.description}</p>
                  )}
                </div>
              </div>
            ))}
            {(c.events ?? []).length === 0 && (
              <p className="text-sm text-gray-400 ml-12">Sin eventos registrados</p>
            )}
          </div>
        </div>
      </div>

      {/* Documentos */}
      {(c.documents ?? []).length > 0 && (
        <div className="card">
          <h2 className="font-semibold text-gray-800 mb-3">Documentos adjuntos</h2>
          <div className="space-y-2">
            {c.documents.map(d => (
              <div key={d.id} className="flex items-center gap-3 p-3 rounded-lg bg-gray-50">
                <Paperclip className="w-4 h-4 text-gray-400 shrink-0" />
                <span className="text-sm text-gray-700 flex-1 truncate">{d.file_name}</span>
                <span className="text-xs text-gray-400">
                  {format(new Date(d.uploaded_at), "d MMM yyyy", { locale: es })}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
