import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Menu, Bell, LogOut, User, ChevronDown } from 'lucide-react'
import { useAuthStore } from '../store/authStore'
import { useAlertStore } from '../store/alertStore'

export default function Navbar({ onMenuClick }) {
  const [profileOpen, setProfileOpen] = useState(false)
  const [alertsOpen,  setAlertsOpen]  = useState(false)
  const { user, logout }   = useAuthStore()
  const { unreadCount, recentAlerts, resetCount } = useAlertStore()
  const navigate = useNavigate()

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  const ROLE_LABEL = { admin: 'Administrador', analyst: 'Analista', viewer: 'Consulta' }

  return (
    <header className="h-14 bg-white border-b border-gray-200 flex items-center px-4 gap-4 sticky top-0 z-10">
      {/* Botón menú móvil */}
      <button
        onClick={onMenuClick}
        className="lg:hidden text-gray-500 hover:text-gray-700"
      >
        <Menu className="w-5 h-5" />
      </button>

      <div className="flex-1" />

      {/* Alertas */}
      <div className="relative">
        <button
          onClick={() => { setAlertsOpen(!alertsOpen); resetCount() }}
          className="relative p-2 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-lg"
        >
          <Bell className="w-5 h-5" />
          {unreadCount > 0 && (
            <span className="absolute top-1 right-1 bg-red-500 text-white text-xs font-bold w-4 h-4 rounded-full flex items-center justify-center">
              {unreadCount > 9 ? '9+' : unreadCount}
            </span>
          )}
        </button>

        {alertsOpen && (
          <div className="absolute right-0 mt-2 w-80 bg-white border border-gray-200 rounded-xl shadow-lg z-50">
            <div className="flex items-center justify-between px-4 py-3 border-b">
              <span className="font-semibold text-sm">Alertas recientes</span>
              <Link to="/alerts" onClick={() => setAlertsOpen(false)}
                className="text-primary-600 text-xs hover:underline">
                Ver todas
              </Link>
            </div>
            {recentAlerts.length === 0 ? (
              <p className="text-center text-gray-400 text-sm py-6">Sin alertas nuevas</p>
            ) : (
              <ul className="divide-y divide-gray-100 max-h-72 overflow-y-auto">
                {recentAlerts.map((a, i) => (
                  <li key={i} className="px-4 py-3 hover:bg-gray-50 cursor-pointer">
                    <p className="text-xs font-medium text-gray-800 truncate">{a.entity_name}</p>
                    <p className="text-xs text-gray-500 truncate">{a.message}</p>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
      </div>

      {/* Perfil */}
      <div className="relative">
        <button
          onClick={() => setProfileOpen(!profileOpen)}
          className="flex items-center gap-2 pl-2 pr-3 py-1.5 rounded-lg hover:bg-gray-100 text-sm"
        >
          <div className="w-7 h-7 rounded-full bg-primary-600 flex items-center justify-center text-white text-xs font-bold">
            {user?.full_name?.charAt(0)?.toUpperCase() ?? 'U'}
          </div>
          <div className="hidden sm:block text-left">
            <p className="font-medium text-gray-800 leading-tight text-xs">{user?.full_name}</p>
            <p className="text-gray-400 text-xs">{ROLE_LABEL[user?.role]}</p>
          </div>
          <ChevronDown className="w-3.5 h-3.5 text-gray-400" />
        </button>

        {profileOpen && (
          <div className="absolute right-0 mt-2 w-48 bg-white border border-gray-200 rounded-xl shadow-lg z-50 py-1">
            <Link to="/profile"
              onClick={() => setProfileOpen(false)}
              className="flex items-center gap-2 px-4 py-2 text-sm text-gray-700 hover:bg-gray-50">
              <User className="w-4 h-4" /> Mi perfil
            </Link>
            <hr className="my-1" />
            <button
              onClick={handleLogout}
              className="flex items-center gap-2 px-4 py-2 text-sm text-red-600 hover:bg-red-50 w-full">
              <LogOut className="w-4 h-4" /> Cerrar sesión
            </button>
          </div>
        )}
      </div>
    </header>
  )
}
