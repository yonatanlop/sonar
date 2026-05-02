import { NavLink } from 'react-router-dom'
import {
  LayoutDashboard, Building2, MessageSquare,
  Bell, Inbox, FileText, Users, Settings2, Radio, UserCircle, Sparkles, Activity, Twitter,
  MapPin, GitCompareArrows, Youtube,
} from 'lucide-react'
import { clsx } from 'clsx'
import { useAuthStore } from '../store/authStore'
import { useAlertStore } from '../store/alertStore'

const NAV_SECTIONS = (isAdmin, isAnalyst, unread, inbox) => [
  {
    label: 'MONITOREO',
    items: [
      { to: '/',        icon: LayoutDashboard,  label: 'Dashboard' },
      { to: '/entities', icon: Building2,        label: 'Entidades' },
      { to: '/mentions', icon: MessageSquare,    label: 'Menciones' },
      { to: '/geo',      icon: MapPin,           label: 'Mapa Geográfico' },
      { to: '/compare',  icon: GitCompareArrows, label: 'Comparar Entidades' },
    ],
  },
  {
    label: 'ALERTAS',
    items: [
      { to: '/alerts', icon: Bell,  label: 'Alertas',  badge: unread },
      { to: '/inbox',  icon: Inbox, label: 'Bandeja',  badge: inbox  },
      ...(isAnalyst ? [{ to: '/settings/rules', icon: Settings2, label: 'Reglas de alerta' }] : []),
    ],
  },
  {
    label: 'HERRAMIENTAS',
    items: [
      { to: '/reports',          icon: FileText,  label: 'Reportes' },
      { to: '/chat',             icon: Sparkles,  label: 'Asistente IA' },
      { to: '/twitter-explorer', icon: Twitter,   label: 'Twitter Explorer' },
      { to: '/youtube-explorer', icon: Youtube,   label: 'YouTube Explorer' },
      { to: '/platforms',        icon: Activity,  label: 'Plataformas' },
    ],
  },
  ...(isAdmin ? [{
    label: 'ADMINISTRACIÓN',
    items: [
      { to: '/admin/users', icon: Users, label: 'Usuarios' },
    ],
  }] : []),
]

export default function Sidebar({ open, onClose }) {
  const isAdmin   = useAuthStore((s) => s.isAdmin())
  const isAnalyst = useAuthStore((s) => s.isAnalyst())
  const unread    = useAlertStore((s) => s.unreadCount)
  const inbox     = useAlertStore((s) => s.inboxCount)

  const sections = NAV_SECTIONS(isAdmin, isAnalyst, unread, inbox)

  return (
    <>
      {/* Overlay móvil */}
      {open && (
        <div
          className="fixed inset-0 bg-black/40 z-20 lg:hidden"
          onClick={onClose}
        />
      )}

      <aside className={clsx(
        'fixed top-0 left-0 h-full w-64 bg-primary-900 text-white z-30 flex flex-col transition-transform duration-200',
        open ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'
      )}>
        {/* Logo */}
        <div className="flex items-center gap-3 px-5 py-5 border-b border-primary-700">
          <div className="bg-primary-500 rounded-lg p-1.5">
            <Radio className="w-5 h-5 text-white" />
          </div>
          <div>
            <span className="font-bold text-lg tracking-tight">SONAR</span>
            <p className="text-primary-300 text-xs leading-none">Monitoreo Reputacional</p>
          </div>
        </div>

        {/* Navegación por secciones */}
        <nav className="flex-1 px-3 py-4 overflow-y-auto space-y-4">
          {sections.map(({ label, items }) => (
            <div key={label}>
              <p className="text-primary-500 text-[10px] font-semibold tracking-widest px-3 mb-1">
                {label}
              </p>
              <div className="space-y-0.5">
                {items.map(({ to, icon: Icon, label: itemLabel, badge }) => (
                  <NavLink
                    key={to}
                    to={to}
                    end={to === '/'}
                    onClick={onClose}
                    className={({ isActive }) => clsx(
                      'flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors',
                      isActive
                        ? 'bg-primary-600 text-white'
                        : 'text-primary-200 hover:bg-primary-800 hover:text-white'
                    )}
                  >
                    <Icon className="w-4 h-4 shrink-0" />
                    <span className="flex-1">{itemLabel}</span>
                    {badge > 0 && (
                      <span className="bg-red-500 text-white text-xs font-bold px-1.5 py-0.5 rounded-full min-w-[1.25rem] text-center">
                        {badge > 99 ? '99+' : badge}
                      </span>
                    )}
                  </NavLink>
                ))}
              </div>
            </div>
          ))}
        </nav>

        {/* Perfil en la parte inferior */}
        <div className="px-3 py-3 border-t border-primary-700">
          <NavLink
            to="/profile"
            onClick={onClose}
            className={({ isActive }) => clsx(
              'flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors',
              isActive
                ? 'bg-primary-600 text-white'
                : 'text-primary-200 hover:bg-primary-800 hover:text-white'
            )}
          >
            <UserCircle className="w-4 h-4 shrink-0" />
            <span>Mi perfil</span>
          </NavLink>
        </div>
      </aside>
    </>
  )
}
