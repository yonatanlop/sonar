import { useState, useCallback, useRef } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  ReactFlow, Background, Controls, MiniMap,
  addEdge, useNodesState, useEdgesState,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { Plus, Trash2, Upload, Network, Users } from 'lucide-react'
import toast from 'react-hot-toast'
import client from '../../../shared/api/client'
import { useAuthStore } from '../../../shared/store/authStore'

const fetchGraph  = () => client.get('/actor-map/graph').then(r => r.data)
const fetchActors = () => client.get('/actor-map/actors').then(r => r.data)
const fetchGroups = () => client.get('/actor-map/groups').then(r => r.data)

const PARTY_COLORS = {
  default: '#6366f1',
}

const ACTOR_TYPE_COLOR = {
  politician:   '#3b82f6',
  organization: '#10b981',
  media:        '#f59e0b',
  influencer:   '#ec4899',
}

const RELATION_COLORS = {
  ally:         '#22c55e',
  opponent:     '#ef4444',
  financed_by:  '#f59e0b',
  member_of:    '#6366f1',
}

function nodeStyle(data) {
  const color = ACTOR_TYPE_COLOR[data.actor_type] ?? '#6366f1'
  return {
    background: color,
    color: '#fff',
    border: `2px solid ${color}`,
    borderRadius: '8px',
    padding: '8px 12px',
    fontSize: '12px',
    fontWeight: 600,
    minWidth: '100px',
    textAlign: 'center',
  }
}

function ActorForm({ onSave, onCancel, isPending }) {
  const [form, setForm] = useState({ name: '', actor_type: 'politician', party: '', position: '', country_code: '' })
  const set = (k, v) => setForm(f => ({ ...f, [k]: v }))
  return (
    <form onSubmit={e => { e.preventDefault(); onSave(form) }} className="space-y-3">
      <div className="grid grid-cols-1 gap-3">
        <div>
          <label className="label text-xs">Nombre</label>
          <input className="input text-sm" value={form.name} onChange={e => set('name', e.target.value)} required />
        </div>
        <div>
          <label className="label text-xs">Tipo</label>
          <select className="input text-sm" value={form.actor_type} onChange={e => set('actor_type', e.target.value)}>
            <option value="politician">Político</option>
            <option value="organization">Organización</option>
            <option value="media">Medio</option>
            <option value="influencer">Influencer</option>
          </select>
        </div>
        <div>
          <label className="label text-xs">Partido / Afiliación</label>
          <input className="input text-sm" value={form.party} onChange={e => set('party', e.target.value)} />
        </div>
        <div>
          <label className="label text-xs">Cargo / Posición</label>
          <input className="input text-sm" value={form.position} onChange={e => set('position', e.target.value)} />
        </div>
      </div>
      <div className="flex gap-2">
        <button type="submit" className="btn-primary text-xs py-1.5 px-3" disabled={isPending}>
          {isPending ? '...' : 'Crear actor'}
        </button>
        <button type="button" className="btn-secondary text-xs py-1.5 px-3" onClick={onCancel}>Cancelar</button>
      </div>
    </form>
  )
}

function RelationForm({ actors, onSave, onCancel, isPending }) {
  const [form, setForm] = useState({ source_id: '', target_id: '', relation_type: 'ally', strength: 1 })
  const set = (k, v) => setForm(f => ({ ...f, [k]: v }))
  return (
    <form onSubmit={e => { e.preventDefault(); onSave(form) }} className="space-y-3">
      <div>
        <label className="label text-xs">Origen</label>
        <select className="input text-sm" value={form.source_id} onChange={e => set('source_id', e.target.value)} required>
          <option value="">Selecciona...</option>
          {actors.map(a => <option key={a.id} value={a.id}>{a.name}</option>)}
        </select>
      </div>
      <div>
        <label className="label text-xs">Destino</label>
        <select className="input text-sm" value={form.target_id} onChange={e => set('target_id', e.target.value)} required>
          <option value="">Selecciona...</option>
          {actors.map(a => <option key={a.id} value={a.id}>{a.name}</option>)}
        </select>
      </div>
      <div>
        <label className="label text-xs">Tipo de relación</label>
        <select className="input text-sm" value={form.relation_type} onChange={e => set('relation_type', e.target.value)}>
          <option value="ally">Aliado</option>
          <option value="opponent">Opositor</option>
          <option value="financed_by">Financiado por</option>
          <option value="member_of">Miembro de</option>
        </select>
      </div>
      <div>
        <label className="label text-xs">Fuerza (1–5)</label>
        <input className="input text-sm" type="number" min={1} max={5} value={form.strength}
          onChange={e => set('strength', Number(e.target.value))} />
      </div>
      <div className="flex gap-2">
        <button type="submit" className="btn-primary text-xs py-1.5 px-3" disabled={isPending}>
          {isPending ? '...' : 'Crear relación'}
        </button>
        <button type="button" className="btn-secondary text-xs py-1.5 px-3" onClick={onCancel}>Cancelar</button>
      </div>
    </form>
  )
}

export default function ActorMap() {
  const qc = useQueryClient()
  const isAnalyst = useAuthStore(s => s.isAnalyst())
  const [panel, setPanel]       = useState(null) // 'actor' | 'relation' | 'list'
  const [selected, setSelected] = useState(null)
  const fileRef = useRef()

  const [nodes, setNodes, onNodesChange] = useNodesState([])
  const [edges, setEdges, onEdgesChange] = useEdgesState([])

  const { data: graphData, isLoading } = useQuery({
    queryKey: ['actor-graph'],
    queryFn: fetchGraph,
    onSuccess: (data) => {
      setNodes(data.nodes.map(n => ({
        id: n.id,
        data: n.data,
        position: { x: Math.random() * 600, y: Math.random() * 400 },
        style: nodeStyle(n.data),
      })))
      setEdges(data.edges.map(e => ({
        id: e.id,
        source: e.source,
        target: e.target,
        label: e.label,
        style: { stroke: RELATION_COLORS[e.data.relation_type] ?? '#94a3b8', strokeWidth: e.data.strength },
        labelStyle: { fontSize: 10 },
      })))
    },
  })

  const { data: actors = [] } = useQuery({ queryKey: ['actors'], queryFn: fetchActors })

  const createActor = useMutation({
    mutationFn: (body) => client.post('/actor-map/actors', body),
    onSuccess: () => { toast.success('Actor creado'); qc.invalidateQueries({ queryKey: ['actor-graph', 'actors'] }); setPanel(null) },
    onError: (e) => toast.error(e?.response?.data?.detail ?? 'Error'),
  })

  const createRelation = useMutation({
    mutationFn: (body) => client.post('/actor-map/relations', body),
    onSuccess: () => { toast.success('Relación creada'); qc.invalidateQueries({ queryKey: ['actor-graph'] }); setPanel(null) },
    onError: (e) => toast.error(e?.response?.data?.detail ?? 'Error'),
  })

  const deleteRelation = useMutation({
    mutationFn: (id) => client.delete(`/actor-map/relations/${id}`),
    onSuccess: () => { toast.success('Relación eliminada'); qc.invalidateQueries({ queryKey: ['actor-graph'] }) },
  })

  const importExcel = useMutation({
    mutationFn: async (file) => {
      const fd = new FormData()
      fd.append('file', file)
      return client.post('/actor-map/import-excel', fd, {
        headers: { 'Content-Type': 'multipart/form-data' },
      }).then(r => r.data)
    },
    onSuccess: (data) => {
      toast.success(`Importado: ${data.created_actors} actores, ${data.created_relations} relaciones`)
      qc.invalidateQueries({ queryKey: ['actor-graph', 'actors'] })
    },
    onError: (e) => toast.error(e?.response?.data?.detail ?? 'Error al importar'),
  })

  const onConnect = useCallback((params) => setEdges(eds => addEdge(params, eds)), [setEdges])

  const onNodeClick = useCallback((_, node) => setSelected(node), [])

  if (isLoading) return <div className="text-center text-gray-400 py-12">Cargando grafo...</div>

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Mapa de Actores</h1>
          <p className="text-gray-500 text-sm mt-0.5">{actors.length} actores · {edges.length} relaciones</p>
        </div>
        {isAnalyst && (
          <div className="flex gap-2 flex-wrap">
            <button className="btn-secondary text-xs py-1.5 px-3" onClick={() => setPanel(panel === 'list' ? null : 'list')}>
              <Users className="w-3.5 h-3.5" /> Lista actores
            </button>
            <button className="btn-secondary text-xs py-1.5 px-3" onClick={() => setPanel(panel === 'actor' ? null : 'actor')}>
              <Plus className="w-3.5 h-3.5" /> Actor
            </button>
            <button className="btn-secondary text-xs py-1.5 px-3" onClick={() => setPanel(panel === 'relation' ? null : 'relation')}>
              <Network className="w-3.5 h-3.5" /> Relación
            </button>
            <button className="btn-secondary text-xs py-1.5 px-3" onClick={() => fileRef.current?.click()}>
              <Upload className="w-3.5 h-3.5" /> Importar Excel
            </button>
            <input ref={fileRef} type="file" accept=".xlsx,.xls" className="hidden"
              onChange={e => { if (e.target.files[0]) importExcel.mutate(e.target.files[0]) }} />
          </div>
        )}
      </div>

      <div className="flex gap-4">
        {/* Panel lateral */}
        {panel && (
          <div className="w-72 shrink-0">
            <div className="card">
              {panel === 'actor' && (
                <>
                  <h2 className="font-semibold text-gray-800 mb-4">Nuevo actor</h2>
                  <ActorForm
                    onSave={(form) => createActor.mutate(form)}
                    onCancel={() => setPanel(null)}
                    isPending={createActor.isPending}
                  />
                </>
              )}
              {panel === 'relation' && (
                <>
                  <h2 className="font-semibold text-gray-800 mb-4">Nueva relación</h2>
                  <RelationForm
                    actors={actors}
                    onSave={(form) => createRelation.mutate(form)}
                    onCancel={() => setPanel(null)}
                    isPending={createRelation.isPending}
                  />
                </>
              )}
              {panel === 'list' && (
                <>
                  <h2 className="font-semibold text-gray-800 mb-3">Actores</h2>
                  <div className="space-y-2 max-h-96 overflow-y-auto">
                    {actors.map(a => (
                      <div key={a.id}
                        className="flex items-center gap-2 p-2 rounded-lg hover:bg-gray-50 cursor-pointer"
                        onClick={() => {
                          const node = nodes.find(n => n.id === a.id)
                          if (node) setSelected(node)
                        }}>
                        <div className="w-2.5 h-2.5 rounded-full shrink-0"
                          style={{ background: ACTOR_TYPE_COLOR[a.actor_type] ?? '#6366f1' }} />
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-medium text-gray-900 truncate">{a.name}</p>
                          <p className="text-xs text-gray-400">{a.party ?? a.actor_type}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                </>
              )}
            </div>

            {/* Panel info del nodo seleccionado */}
            {selected && (
              <div className="card mt-4">
                <div className="flex items-center justify-between mb-3">
                  <h2 className="font-semibold text-gray-800">Actor seleccionado</h2>
                  <button onClick={() => setSelected(null)} className="text-gray-400 hover:text-gray-600 text-xs">✕</button>
                </div>
                <p className="font-medium text-gray-900">{selected.data.label}</p>
                <p className="text-xs text-gray-500 mt-1">{selected.data.actor_type}</p>
                {selected.data.party && <p className="text-xs text-gray-500">{selected.data.party}</p>}
                {selected.data.position && <p className="text-xs text-gray-500">{selected.data.position}</p>}
                {/* Relaciones del nodo */}
                <div className="mt-3">
                  <p className="text-xs font-semibold text-gray-500 mb-1">Relaciones</p>
                  {edges
                    .filter(e => e.source === selected.id || e.target === selected.id)
                    .map(e => {
                      const other = e.source === selected.id
                        ? nodes.find(n => n.id === e.target)
                        : nodes.find(n => n.id === e.source)
                      return (
                        <div key={e.id} className="flex items-center justify-between text-xs text-gray-600 py-1 border-b border-gray-50">
                          <span>{e.source === selected.id ? '→' : '←'} {other?.data.label}</span>
                          <div className="flex items-center gap-2">
                            <span className="text-gray-400">{e.label}</span>
                            {isAnalyst && (
                              <button onClick={() => deleteRelation.mutate(e.id)}
                                className="text-red-400 hover:text-red-600">
                                <Trash2 className="w-3 h-3" />
                              </button>
                            )}
                          </div>
                        </div>
                      )
                    })}
                </div>
              </div>
            )}
          </div>
        )}

        {/* Grafo react-flow */}
        <div className="flex-1 bg-gray-100 rounded-xl overflow-hidden" style={{ height: '70vh' }}>
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            onNodeClick={onNodeClick}
            fitView
          >
            <Background />
            <Controls />
            <MiniMap />
          </ReactFlow>
        </div>
      </div>

      {/* Leyenda */}
      <div className="card p-3">
        <p className="text-xs font-semibold text-gray-500 mb-2">LEYENDA</p>
        <div className="flex flex-wrap gap-4 text-xs">
          <div>
            <p className="text-gray-400 mb-1">Tipo de actor</p>
            <div className="flex flex-wrap gap-2">
              {Object.entries(ACTOR_TYPE_COLOR).map(([k, c]) => (
                <span key={k} className="flex items-center gap-1">
                  <span className="w-2.5 h-2.5 rounded" style={{ background: c }} />
                  <span className="text-gray-600">{k}</span>
                </span>
              ))}
            </div>
          </div>
          <div>
            <p className="text-gray-400 mb-1">Tipo de relación</p>
            <div className="flex flex-wrap gap-2">
              {Object.entries(RELATION_COLORS).map(([k, c]) => (
                <span key={k} className="flex items-center gap-1">
                  <span className="w-5 h-0.5 inline-block" style={{ background: c }} />
                  <span className="text-gray-600">{k}</span>
                </span>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
