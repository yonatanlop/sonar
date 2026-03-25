import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Plus, UserCheck, UserX } from 'lucide-react'
import toast from 'react-hot-toast'
import client from '../api/client'

const fetchUsers  = () => client.get('/users').then(r => r.data)

const ROLE_LABEL  = { admin: 'Administrador', analyst: 'Analista', viewer: 'Consulta' }
const ROLE_COLOR  = { admin: 'bg-purple-100 text-purple-800', analyst: 'bg-blue-100 text-blue-800', viewer: 'bg-gray-100 text-gray-700' }

export default function Users() {
  const qc = useQueryClient()
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState({ username: '', email: '', full_name: '', password: '', role: 'viewer' })

  const { data: users = [], isLoading } = useQuery({ queryKey: ['users'], queryFn: fetchUsers })

  const create = useMutation({
    mutationFn: (body) => client.post('/users', body),
    onSuccess: () => {
      toast.success('Usuario creado')
      qc.invalidateQueries({ queryKey: ['users'] })
      setShowForm(false)
      setForm({ username: '', email: '', full_name: '', password: '', role: 'viewer' })
    },
  })

  const toggleActive = useMutation({
    mutationFn: ({ id, active }) => client.put(`/users/${id}`, { active: !active }),
    onSuccess: () => {
      toast.success('Usuario actualizado')
      qc.invalidateQueries({ queryKey: ['users'] })
    },
  })

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Usuarios</h1>
          <p className="text-gray-500 text-sm mt-0.5">Gestión de acceso al sistema</p>
        </div>
        <button onClick={() => setShowForm(!showForm)} className="btn-primary">
          <Plus className="w-4 h-4" /> Nuevo usuario
        </button>
      </div>

      {/* Formulario */}
      {showForm && (
        <div className="card border-primary-200 border-2">
          <h2 className="font-semibold mb-4">Nuevo usuario</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="label">Nombre completo *</label>
              <input className="input" placeholder="Ana López"
                value={form.full_name} onChange={e => setForm(f => ({ ...f, full_name: e.target.value }))} />
            </div>
            <div>
              <label className="label">Usuario *</label>
              <input className="input" placeholder="ana.lopez"
                value={form.username} onChange={e => setForm(f => ({ ...f, username: e.target.value }))} />
            </div>
            <div>
              <label className="label">Email *</label>
              <input className="input" type="email" placeholder="ana@ejemplo.com"
                value={form.email} onChange={e => setForm(f => ({ ...f, email: e.target.value }))} />
            </div>
            <div>
              <label className="label">Contraseña temporal *</label>
              <input className="input" type="password" placeholder="••••••••"
                value={form.password} onChange={e => setForm(f => ({ ...f, password: e.target.value }))} />
            </div>
            <div>
              <label className="label">Rol *</label>
              <select className="input" value={form.role}
                onChange={e => setForm(f => ({ ...f, role: e.target.value }))}>
                <option value="viewer">Consulta</option>
                <option value="analyst">Analista</option>
                <option value="admin">Administrador</option>
              </select>
            </div>
          </div>
          <div className="flex gap-2 mt-4">
            <button onClick={() => create.mutate(form)}
              disabled={create.isPending || !form.username || !form.email || !form.full_name || !form.password}
              className="btn-primary">
              {create.isPending ? 'Guardando...' : 'Crear usuario'}
            </button>
            <button onClick={() => setShowForm(false)} className="btn-secondary">Cancelar</button>
          </div>
        </div>
      )}

      {/* Tabla de usuarios */}
      {isLoading ? (
        <div className="text-center text-gray-400 py-12">Cargando usuarios...</div>
      ) : (
        <div className="card p-0 overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-100">
              <tr>
                <th className="text-left px-5 py-3 font-medium text-gray-600">Usuario</th>
                <th className="text-left px-5 py-3 font-medium text-gray-600">Email</th>
                <th className="text-left px-5 py-3 font-medium text-gray-600">Rol</th>
                <th className="text-left px-5 py-3 font-medium text-gray-600">Estado</th>
                <th className="text-left px-5 py-3 font-medium text-gray-600">Último acceso</th>
                <th className="px-5 py-3" />
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {users.map(user => (
                <tr key={user.id} className="hover:bg-gray-50">
                  <td className="px-5 py-3">
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded-full bg-primary-100 flex items-center justify-center text-primary-700 font-bold text-xs">
                        {user.full_name?.charAt(0)}
                      </div>
                      <div>
                        <p className="font-medium text-gray-900">{user.full_name}</p>
                        <p className="text-xs text-gray-400">@{user.username}</p>
                      </div>
                    </div>
                  </td>
                  <td className="px-5 py-3 text-gray-600">{user.email}</td>
                  <td className="px-5 py-3">
                    <span className={`badge ${ROLE_COLOR[user.role]}`}>{ROLE_LABEL[user.role]}</span>
                  </td>
                  <td className="px-5 py-3">
                    <span className={`badge ${user.active ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'}`}>
                      {user.active ? 'Activo' : 'Inactivo'}
                    </span>
                  </td>
                  <td className="px-5 py-3 text-gray-400 text-xs">
                    {user.last_login ? new Date(user.last_login).toLocaleDateString('es') : 'Nunca'}
                  </td>
                  <td className="px-5 py-3 text-right">
                    <button
                      onClick={() => toggleActive.mutate({ id: user.id, active: user.active })}
                      className={`text-xs px-3 py-1 rounded-lg border ${user.active
                        ? 'border-red-200 text-red-600 hover:bg-red-50'
                        : 'border-green-200 text-green-600 hover:bg-green-50'}`}>
                      {user.active
                        ? <><UserX className="w-3.5 h-3.5 inline mr-1" />Desactivar</>
                        : <><UserCheck className="w-3.5 h-3.5 inline mr-1" />Activar</>}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
