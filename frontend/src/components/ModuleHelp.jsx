import InfoTip from './InfoTip'
import { MODULE_HELP } from '../data/moduleHelp'

// Ícono de ayuda junto al título de un módulo: explica para qué sirve. Los textos viven en
// data/moduleHelp.js (un solo lugar para revisarlos).
export default function ModuleHelp({ id }) {
  const text = MODULE_HELP[id]
  if (!text) return null
  return (
    <span className="ml-2 inline-flex align-middle">
      <InfoTip text={text} align="left" below wide />
    </span>
  )
}
