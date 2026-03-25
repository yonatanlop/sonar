import { useEffect } from 'react'
import toast from 'react-hot-toast'
import { useAlertStore } from '../store/alertStore'
import { useAuthStore } from '../store/authStore'

const SEVERITY_ICON = { low: 'ℹ️', medium: '⚠️', high: '🔴', critical: '🚨' }

export function useAlertStream() {
  const { addAlert } = useAlertStore()
  const isAuth = useAuthStore((s) => s.isAuth())

  useEffect(() => {
    if (!isAuth) return

    const token = localStorage.getItem('sonar_token')
    const source = new EventSource(`/api/v1/alerts/stream?token=${token}`)

    source.addEventListener('new_alert', (e) => {
      try {
        const alert = JSON.parse(e.data)
        addAlert(alert)

        // Mostrar toast según severidad
        const icon = SEVERITY_ICON[alert.severity] || '🔔'
        const msg = `${icon} ${alert.entity_name}: ${alert.message.slice(0, 80)}`

        if (alert.severity === 'critical') {
          toast.error(msg, { duration: 8000 })
        } else if (alert.severity === 'high') {
          toast.error(msg, { duration: 6000, style: { background: '#ea580c', color: '#fff' } })
        } else {
          toast(msg, { duration: 4000 })
        }
      } catch {
        // ignorar mensajes malformados
      }
    })

    source.onerror = () => source.close()

    return () => source.close()
  }, [isAuth, addAlert])
}
