import { Info } from 'lucide-react'

// Ícono de ayuda con tooltip al pasar el mouse o al tocarlo/enfocarlo (móvil y teclado).
// Explica qué representa una caja, columna o módulo.
//   align: hacia dónde se abre el texto respecto al ícono ('center' | 'left' | 'right')
//   below: abre el texto debajo del ícono (útil junto a títulos en la parte alta de la página)
//   wide:  cuadro más ancho, para textos largos
export default function InfoTip({ text, align = 'center', below = false, wide = false }) {
  const pos = align === 'left'
    ? 'left-0'
    : align === 'right'
    ? 'right-0'
    : 'left-1/2 -translate-x-1/2'
  return (
    <span className="relative inline-flex items-center group align-middle focus:outline-none" tabIndex={0}>
      <Info className="w-3.5 h-3.5 text-gray-300 hover:text-gray-500 group-focus:text-gray-500 cursor-help" />
      <span
        role="tooltip"
        className={`pointer-events-none absolute ${below ? 'top-full mt-1.5' : 'bottom-full mb-1.5'} ${wide ? 'w-72 sm:w-80' : 'w-60'} z-30 ${pos}
                    opacity-0 group-hover:opacity-100 group-focus:opacity-100 transition-opacity duration-150
                    bg-gray-900 text-white text-xs font-normal normal-case leading-snug text-left
                    rounded-lg px-3 py-2 shadow-lg`}
      >
        {text}
      </span>
    </span>
  )
}
