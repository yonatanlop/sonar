/**
 * Facebook Explorer — monitores por palabra clave/tema o página/perfil.
 */
import { Facebook, Search, FileText } from 'lucide-react'
import PlatformExplorer from '../components/PlatformExplorer'

const THEME = {
  iconBg: 'bg-blue-100', iconText: 'text-blue-600',
  addBtn: 'bg-blue-600 hover:bg-blue-700',
  selectedBg: 'bg-blue-50 border-blue-200',
  selectedIconBg: 'bg-blue-100', selectedIconText: 'text-blue-600',
  chevron: 'text-blue-400',
  linkHover: 'hover:text-blue-600',
  spinner: 'text-blue-400',
  ring: 'focus:ring-blue-400',
  modalBtn: 'bg-blue-600 hover:bg-blue-700',
  modalTypeActive: 'bg-blue-50 border-blue-400 text-blue-700',
}

const FEED_TYPES = [
  { value: 'keyword', icon: Search,   label: 'Palabra clave', groupLabel: 'Palabras clave', placeholder: 'reforma pensional' },
  { value: 'page',    icon: FileText, label: 'Página',        groupLabel: 'Páginas',        placeholder: 'Nombre o usuario de la página' },
]

export default function FacebookExplorer() {
  return (
    <PlatformExplorer
      apiBase="/facebook-feeds"
      title="Facebook Explorer"
      subtitle="Monitorea temas y páginas de Facebook"
      HeaderIcon={Facebook}
      itemNoun="publicaciones"
      feedTypes={FEED_TYPES}
      theme={THEME}
    />
  )
}
