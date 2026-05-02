import { useEffect } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import { useAlertStore } from '../store/alertStore'
import { useAuthStore } from '../store/authStore'

const SEVERITY_ICON = { low: 'ℹ️', medium: '⚠️', high: '🔴', critical: '🚨' }

export function useAlertStream() {
  const { addAlert, incrementInbox } = useAlertStore()
  const isAuth = useAuthStore((s) => s.isAuth())
  const qc = useQueryClient()

  useEffect(() => {
    if (!isAuth) return

    const token = localStorage.getItem('sonar_token')
    const source = new EventSource(`/api/v1/alerts/stream?token=${token}`)

    source.addEventListener('new_alert', (e) => {
      try {
        const alert = JSON.parse(e.data)

        if (alert.rule_type === 'negative_mention') {
          // Canal bandeja: no va a la campana, va al contador de inbox
          incrementInbox()
          qc.invalidateQueries({ queryKey: ['inbox'] })
          qc.invalidateQueries({ queryKey: ['inbox-count'] })
          const icon = alert.severity === 'high' ? '🔴' : '⚠️'
          toast(`${icon} Mención negativa — ${alert.entity_name}`, { duration: 4000 })
        } else {
          // Canal campana: flujo existente
          addAlert(alert)
          const icon = SEVERITY_ICON[alert.severity] || '🔔'
          const msg = `${icon} ${alert.entity_name}: ${alert.message.slice(0, 80)}`
          if (alert.severity === 'critical') {
            toast.error(msg, { duration: 8000 })
          } else if (alert.severity === 'high') {
            toast.error(msg, { duration: 6000, style: { background: '#ea580c', color: '#fff' } })
          } else {
            toast(msg, { duration: 4000 })
          }
        }
      } catch {
        // ignorar mensajes malformados
      }
    })

    source.onerror = () => source.close()

    return () => source.close()
  }, [isAuth, addAlert, incrementInbox, qc])
}
