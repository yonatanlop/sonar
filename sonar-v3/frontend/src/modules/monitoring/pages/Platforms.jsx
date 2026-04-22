import { useQuery } from '@tanstack/react-query'
import client from '../../../shared/api/client'

const PLATFORM_ICON = { twitter: '🐦', reddit: '🤖', youtube: '▶️', rss: '📰', instagram: '📸', facebook: '👥' }

export default function Platforms() {
  const { data: platforms = [], isLoading } = useQuery({
    queryKey: ['platforms'],
    queryFn: () => client.get('/platforms').then(r => r.data),
  })

  if (isLoading) return <div className="text-center text-gray-400 py-12">Cargando...</div>

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-gray-900">Plataformas</h1>
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
        {platforms.map(p => (
          <div key={p.id} className="card flex items-center gap-4">
            <span className="text-3xl">{PLATFORM_ICON[p.code] ?? '🌐'}</span>
            <div>
              <p className="font-semibold text-gray-900">{p.name}</p>
              <p className="text-xs text-gray-400">{p.code}</p>
              <span className={`badge mt-1 ${p.active ? 'badge-positive' : 'badge-neutral'}`}>
                {p.active ? 'Activa' : 'Inactiva'}
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
