import { Info } from 'lucide-react'

// Ícono de ayuda con tooltip al pasar el mouse. Explica qué representa cada caja o columna.
export default function InfoTip({ text, align = 'center', below = false }) {
  const pos = align === 'left'
    ? 'left-0'
    : align === 'right'
    ? 'right-0'
    : 'left-1/2 -translate-x-1/2'
  return (
    <span className="relative inline-flex items-center group align-middle">
      <Info className="w-3.5 h-3.5 text-gray-300 hover:text-gray-500 cursor-help" />
      <span
        role="tooltip"
        className={`pointer-events-none absolute ${below ? 'top-full mt-1.5' : 'bottom-full mb-1.5'} w-60 z-30 ${pos}
                    opacity-0 group-hover:opacity-100 transition-opacity duration-150
                    bg-gray-900 text-white text-xs font-normal normal-case leading-snug text-left
                    rounded-lg px-3 py-2 shadow-lg`}
      >
        {text}
      </span>
    </span>
  )
}
