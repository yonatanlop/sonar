// Utilidades compartidas de las pestañas de Rizoma (fechas en hora de Colombia)

export const MEDIUMS = ['X', 'Facebook', 'Instagram', 'TikTok', 'YouTube', 'Threads', 'Sitio Web']

export const MEDIUM_BADGE = {
  X: 'bg-sky-100 text-sky-700',
  Facebook: 'bg-blue-100 text-blue-700',
  Instagram: 'bg-pink-100 text-pink-700',
  TikTok: 'bg-gray-800 text-cyan-300',
  YouTube: 'bg-red-100 text-red-700',
  Threads: 'bg-gray-100 text-gray-700',
  'Sitio Web': 'bg-emerald-100 text-emerald-700',
}

const CO = 'America/Bogota'

// Fecha y hora (o "Sin fecha") en hora de Colombia
export function fmtDateTime(dt) {
  if (!dt) return 'Sin fecha'
  return new Date(dt).toLocaleString('es-CO', {
    timeZone: CO, day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit',
  })
}

// Solo fecha en hora de Colombia
export function fmtDay(dt) {
  if (!dt) return 'Sin fecha'
  return new Date(dt).toLocaleDateString('es-CO', { timeZone: CO, day: '2-digit', month: 'short', year: 'numeric' })
}

// 'AAAA-MM-DD' -> 'DD/MM/AAAA' (sin pasar por Date: evita corrimientos de zona horaria)
export function fmtIsoDay(s) {
  return s ? s.split('-').reverse().join('/') : ''
}

const MONTHS = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic']

// Etiqueta del eje según la granularidad; `start` es 'AAAA-MM-DD' (inicio del período)
export function bucketLabel(start, granularity) {
  const [y, m, d] = start.split('-')
  if (granularity === 'month') return `${MONTHS[Number(m) - 1]} ${y}`
  if (granularity === 'week') return `Sem ${d}/${m}`
  return `${d}/${m}`
}
