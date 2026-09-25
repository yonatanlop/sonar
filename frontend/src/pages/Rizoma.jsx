/**
 * Rizoma — centro de seguimiento de cuentas hostiles y ataques.
 * Reúne en un solo lugar (con pestañas según el rol):
 *   Publicaciones · Cuentas de atacantes (con historial) · Balance de denuncias · Cerradas ·
 *   Grupos a cerrar · Seguimiento a caso · Reporte mensual.
 */
import { useSearchParams } from 'react-router-dom'
import ModuleHelp from '../components/ModuleHelp'
import { RIZOMA_TAB_HELP } from '../data/moduleHelp'
import { ShieldAlert } from 'lucide-react'
import { clsx } from 'clsx'
import { useAuthStore } from '../store/authStore'
import RizomaFeed from '../components/rizoma/RizomaFeed'
import RizomaAccounts from '../components/rizoma/RizomaAccounts'
import RizomaBalance from '../components/rizoma/RizomaBalance'
import RizomaClosed from '../components/rizoma/RizomaClosed'
import FacebookGroups from './FacebookGroups'
import Cases from './Cases'
import CaseReports from './CaseReports'

// role: quién ve la pestaña (los permisos de cada módulo se mantienen)
const TABS = [
  { key: 'feed',     label: 'Publicaciones',        role: 'all',     Component: RizomaFeed },
  { key: 'accounts', label: 'Cuentas de atacantes', role: 'admin',   Component: RizomaAccounts },
  { key: 'balance',  label: 'Balance de denuncias', role: 'admin',   Component: RizomaBalance },
  { key: 'closed',   label: 'Cerradas',             role: 'admin',   Component: RizomaClosed },
  { key: 'groups',   label: 'Grupos a cerrar',      role: 'analyst', Component: FacebookGroups },
  { key: 'cases',    label: 'Seguimiento a caso',   role: 'admin',   Component: Cases },
  { key: 'monthly',  label: 'Reporte mensual',      role: 'admin',   Component: CaseReports },
]

// Pestañas cuyo contenido ya trae su propio título con ayuda (ModuleHelp)
const HAS_OWN_HELP = new Set(['groups', 'cases', 'monthly'])

export default function Rizoma() {
  const isAdmin   = useAuthStore((s) => s.isAdmin())
  const isAnalyst = useAuthStore((s) => s.isAnalyst())
  const [params, setParams] = useSearchParams()

  const allowed = TABS.filter(t => t.role === 'all' || (t.role === 'analyst' && isAnalyst) || (t.role === 'admin' && isAdmin))
  const active  = allowed.find(t => t.key === params.get('tab')) ?? allowed[0]
  const Active  = active.Component

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <ShieldAlert className="w-6 h-6 text-red-600" />
        <div>
          <h1 className="text-xl font-bold text-gray-900">Rizoma <ModuleHelp id="rizoma" /></h1>
          <p className="text-sm text-gray-500">Cuentas hostiles, denuncias y cierres en un solo lugar</p>
        </div>
      </div>

      {allowed.length > 1 && (
        <div className="flex gap-1 overflow-x-auto overflow-y-hidden border-b border-gray-200">
          {allowed.map(t => (
            <button
              key={t.key}
              onClick={() => setParams({ tab: t.key }, { replace: true })}
              title={RIZOMA_TAB_HELP[t.key]}
              className={clsx(
                'px-4 py-2 text-sm font-medium whitespace-nowrap border-b-2 -mb-px transition-colors',
                t.key === active.key
                  ? 'border-red-600 text-red-700'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              )}
            >
              {t.label}
            </button>
          ))}
        </div>
      )}

      {/* Para qué sirve la pestaña activa (las que traen su propio título ya muestran su ayuda con el ícono ⓘ) */}
      {!HAS_OWN_HELP.has(active.key) && RIZOMA_TAB_HELP[active.key] && (
        <p className="text-xs text-gray-500 bg-gray-50 border border-gray-100 rounded-lg px-3 py-2">
          <span className="font-semibold text-gray-600">¿Para qué sirve? </span>{RIZOMA_TAB_HELP[active.key]}
        </p>
      )}

      <Active />
    </div>
  )
}
