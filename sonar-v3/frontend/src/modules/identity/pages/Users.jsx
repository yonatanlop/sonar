import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { UserPlus, Pencil, Trash2 } from 'lucide-react'
import toast from 'react-hot-toast'
import client from '../../../shared/api/client'

const fetchUsers = () => client.get('/users').then(r => r.data)

const ROLES = ['viewer', 'analyst', 'admin']
const ROLE_LABEL = { admin: 'Administrador', analyst: 'Analista', viewer: 'Consulta' }

function UserForm({ initial, onSave, onCancel, isPending }) {
  const [form, setForm] = useState(initial ?? { username: '', email: '', full_name: '', role: 'viewer', password: '' })
  const set = (k, v) => setForm(f => ({ ...f, [k]: v }))

  return (
    <form onSubmit={e => { e.preventDefault(); onSave(form) }}
      className="space-y-3 p-4 border border-gray-200 rounded-xl bg-gray-50">
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <div>
          <label className="label">Nombre completo</label>
          <input className="input" value={form.full_name} onChange={e => set('full_name', e.target.value)} required />
        </div>
        <div>
          <label className="label">Usuario</label>
          <input className="input" value={form.username} onChange={e => set('username', e.target.value)} required />
        </div>
        <div>
          <label className="label">Email</label>
          <input className="input" type="email" value={form.email} onChange={e => set('email', e.target.value)} required />
        </div>
        <div>
          <label className="label">Rol</label>
          <select className="input" value={form.role} onChange={e => set('role', e.target.value)}>
            {ROLES.map(r => <option key={r} value={r}>{ROLE_LABEL[r]}</option>)}
          </select>
        </div>
        {!initial && (
          <div className="sm:col-span-2">
            <label className="label">Contraseña</label>
            <input className="input" type="password" value={form.password} onChange={e => set('password', e.target.value)} required />
          </div>
        )}
      </div>
      <div className="flex gap-2">
        <button type="submit" className="btn-primary" disabled={isPending}>
          {isPending ? 'Guardando...' : initial ? 'Actualizar' : 'Crear usuario'}
        </button>
        <button type="button" className="btn-secondary" onClick={onCancel}>Cancelar</button>
      </div>
    </form>
  )
}

export default function Users() {
  const qc = useQueryClient()
  const [showForm, setShowForm] = useState(false)
  const [editing, setEditing]   = useState(null)

  const { data = [], isLoading } = useQuery({ queryKey: ['users'], queryFn: fetchUsers })

  const create = useMutation({
    mutationFn: (body) => client.post('/users', body),
    onSuccess: () => { toast.success('Usuario creado'); qc.invalidateQueries({ queryKey: ['users'] }); setShowForm(false) },
    onError:   (e) => toast.error(e?.response?.data?.detail ?? 'Error'),
  })

  const update = useMutation({
    mutationFn: ({ id, ...body }) => client.patch(`/users/${id}`, body),
    onSuccess: () => { toast.success('Usuario actualizado'); qc.invalidateQueries({ queryKey: ['users'] }); setEditing(null) },
    onError:   (e) => toast.error(e?.response?.data?.detail ?? 'Error'),
  })

  const deactivate = useMutation({
    mutationFn: (id) => client.patch(`/users/${id}`, { active: false }),
    onSuccess: () => { toast.success('Usuario desactivado'); qc.invalidateQueries({ queryKey: ['users'] }) },
  })

  if (isLoading) return <div className="text-center text-gray-400 py-12">Cargando...</div>

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Usuarios</h1>
        {!showForm && (
          <button className="btn-primary" onClick={() => setShowForm(true)}>
            <UserPlus className="w-4 h-4" /> Nuevo usuario
          </button>
        )}
      </div>

      {showForm && (
        <UserForm
          onSave={(form) => create.mutate(form)}
          onCancel={() => setShowForm(false)}
          isPending={create.isPending}
        />
      )}

      <div className="card p-0 overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b border-gray-100">
            <tr>
              {['Nombre', 'Usuario', 'Email', 'Rol', 'Estado', ''].map(h => (
                <th key={h} className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider">
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-50">
            {data.map(u => (
              <tr key={u.id}>
                {editing?.id === u.id ? (
                  <td colSpan={6} className="px-4 py-3">
                    <UserForm
                      initial={editing}
                      onSave={(form) => update.mutate({ id: u.id, ...form })}
                      onCancel={() => setEditing(null)}
                      isPending={update.isPending}
                    />
                  </td>
                ) : (
                  <>
                    <td className="px-4 py-3 font-medium text-gray-900">{u.full_name}</td>
                    <td className="px-4 py-3 text-gray-600">@{u.username}</td>
                    <td className="px-4 py-3 text-gray-600">{u.email}</td>
                    <td className="px-4 py-3">
                      <span className="badge badge-low">{ROLE_LABEL[u.role]}</span>
                    </td>
                    <td className="px-4 py-3">
                      <span className={`badge ${u.active ? 'badge-positive' : 'badge-neutral'}`}>
                        {u.active ? 'Activo' : 'Inactivo'}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex gap-2">
                        <button onClick={() => setEditing(u)} className="text-gray-400 hover:text-primary-600">
                          <Pencil className="w-4 h-4" />
                        </button>
                        {u.active && (
                          <button onClick={() => deactivate.mutate(u.id)} className="text-gray-400 hover:text-red-600">
                            <Trash2 className="w-4 h-4" />
                          </button>
                        )}
                      </div>
                    </td>
                  </>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
