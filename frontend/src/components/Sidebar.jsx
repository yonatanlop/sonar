import { useState } from 'react'
import { NavLink } from 'react-router-dom'
import {
  LayoutDashboard, Building2, MessageSquare,
  Bell, Inbox, FileText, Users, Settings2, Radio, UserCircle, Activity, Twitter,
  GitCompareArrows, Youtube, ChevronDown, ScrollText, ShieldAlert, Scale, Reply, Search, ScanSearch, MessageSquareReply, Wand2,
  Facebook, Instagram, Music2, UsersRound, FolderSearch,
} from 'lucide-react'
import { clsx } from 'clsx'
import { useAuthStore } from '../store/authStore'
import { useAlertStore } from '../store/alertStore'

const NAV_SECTIONS = (isAdmin, isAnalyst, isSuperAdmin, unread, inbox) => [
  {
    id:    'monitoreo',
    label: 'MONITOREO',
    items: [
      { to: '/',         icon: LayoutDashboard,  label: 'Dashboard' },
      { to: '/entities', icon: Building2,         label: 'Líderes/Instituciones/Keywords' },
      { to: '/mentions', icon: MessageSquare,     label: 'Menciones' },
      { to: '/compare',  icon: GitCompareArrows,  label: 'Comparar alertas' },
    ],
  },
  {
    id:    'alertas',
    label: 'ALERTAS',
    items: [
      { to: '/alerts',  icon: Bell,        label: 'Alertas',  badge: unread },
      { to: '/inbox',   icon: Inbox,       label: 'Bandeja',  badge: inbox  },
      { to: '/rizoma',  icon: ShieldAlert, label: 'Rizoma' },
      { to: '/legal',   icon: Scale,       label: 'Jurídico' },
      ...(isAnalyst ? [{ to: '/grupos', icon: UsersRound, label: 'Grupos a cerrar' }] : []),
      ...(isAnalyst ? [{ to: '/settings/rules', icon: Settings2, label: 'Reglas de alerta' }] : []),
    ],
  },
  {
    id:    'herramientas',
    label: 'HERRAMIENTAS',
    items: [
      { to: '/reports',          icon: FileText,  label: 'Reportes' },
      ...(isAnalyst ? [{ to: '/topic-keywords', icon: Wand2, label: 'Generar Keywords (IA)' }] : []),
      { to: '/twitter-explorer', icon: Twitter,   label: 'Twitter Explorer' },
      { to: '/youtube-explorer', icon: Youtube,   label: 'YouTube Explorer' },
      { to: '/facebook-explorer',  icon: Facebook,  label: 'Facebook Explorer' },
      { to: '/instagram-explorer', icon: Instagram, label: 'Instagram Explorer' },
      { to: '/tiktok-explorer',    icon: Music2,    label: 'TikTok Explorer' },
      { to: '/response-tool',    icon: Reply,      label: 'Herramienta de Respuesta' },
      { to: '/media-search',     icon: ScanSearch, label: 'Búsqueda por Imagen' },
      { to: '/platforms',        icon: Activity,  label: 'Plataformas' },
    ],
  },
  // Sección propia. Hoy solo admin; para abrir a más roles cambiar este gate
  // por `isAnalyst` (y CASE_MANAGER_ROLES en el backend + la ruta en App.jsx).
  ...(isAdmin ? [{
    id:    'seguimiento',
    label: 'SEGUIMIENTO',
    items: [
      { to: '/cases', icon: FolderSearch, label: 'Seguimiento a caso' },
    ],
  }] : []),
  ...(isAdmin ? [{
    id:    'administracion',
    label: 'ADMINISTRACIÓN',
    items: [
      { to: '/admin/users',          icon: Users,              label: 'Usuarios' },
      { to: '/admin/audit',          icon: ScrollText,          label: 'Auditoría' },
      { to: '/admin/reply-accounts', icon: MessageSquareReply,  label: 'Cuentas de Respuesta' },
      ...(isSuperAdmin ? [{ to: '/admin/twitter-search', icon: Search, label: 'Búsqueda Twitter' }] : []),
    ],
  }] : []),
]

export default function Sidebar({ open, onClose }) {
  const isAdmin      = useAuthStore((s) => s.isAdmin())
  const isAnalyst    = useAuthStore((s) => s.isAnalyst())
  const isSuperAdmin = useAuthStore((s) => s.isSuperAdmin())
  const unread    = useAlertStore((s) => s.unreadCount)
  const inbox     = useAlertStore((s) => s.inboxCount)

  const [collapsed, setCollapsed] = useState(() => {
    try {
      const saved = localStorage.getItem('sidebar_collapsed')
      return saved ? JSON.parse(saved) : { herramientas: true }
    } catch { return { herramientas: true } }
  })

  const toggleSection = (id) => {
    const next = { ...collapsed, [id]: !collapsed[id] }
    setCollapsed(next)
    localStorage.setItem('sidebar_collapsed', JSON.stringify(next))
  }

  const sections = NAV_SECTIONS(isAdmin, isAnalyst, isSuperAdmin, unread, inbox)

  return (
    <>
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
            <p className="text-primary-300 text-xs leading-none">v3.0 · Monitoreo Reputacional</p>
          </div>
        </div>

        {/* Navegación */}
        <nav className="flex-1 px-3 py-4 overflow-y-auto space-y-1">
          {sections.map(({ id, label, items }) => {
            const isCollapsed = !!collapsed[id]
            return (
              <div key={id}>
                <button
                  onClick={() => toggleSection(id)}
                  className="w-full flex items-center justify-between px-3 py-1.5 mb-0.5 rounded hover:bg-primary-800 group"
                >
                  <span className="text-primary-500 group-hover:text-primary-400 text-[10px] font-semibold tracking-widest">
                    {label}
                  </span>
                  <ChevronDown className={clsx(
                    'w-3 h-3 text-primary-600 group-hover:text-primary-400 transition-transform duration-200',
                    isCollapsed && '-rotate-90'
                  )} />
                </button>

                <div className={clsx(
                  'overflow-hidden transition-all duration-200',
                  isCollapsed ? 'max-h-0' : 'max-h-[1200px]'
                )}>
                  <div className="space-y-0.5 pb-2">
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
              </div>
            )
          })}
        </nav>

        {/* Perfil */}
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
