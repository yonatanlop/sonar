/**
 * TikTok Explorer — monitores por palabra clave, hashtag o creador/usuario.
 */
import { Music2, Search, Hash, User } from 'lucide-react'
import PlatformExplorer from '../components/PlatformExplorer'

const THEME = {
  iconBg: 'bg-gray-900', iconText: 'text-cyan-400',
  addBtn: 'bg-gray-900 hover:bg-black',
  selectedBg: 'bg-cyan-50 border-cyan-200',
  selectedIconBg: 'bg-gray-900', selectedIconText: 'text-cyan-400',
  chevron: 'text-cyan-500',
  linkHover: 'hover:text-cyan-600',
  spinner: 'text-cyan-500',
  ring: 'focus:ring-cyan-400',
  modalBtn: 'bg-gray-900 hover:bg-black',
  modalTypeActive: 'bg-cyan-50 border-cyan-400 text-cyan-700',
}

const FEED_TYPES = [
  { value: 'keyword', icon: Search, label: 'Palabra clave', groupLabel: 'Palabras clave', placeholder: 'reforma pensional' },
  { value: 'hashtag', icon: Hash,   label: 'Hashtag',       groupLabel: 'Hashtags',       placeholder: 'mira (sin #)' },
  { value: 'creator', icon: User,   label: 'Creador',       groupLabel: 'Creadores',      placeholder: 'usuario (sin @)' },
]

export default function TiktokExplorer() {
  return (
    <PlatformExplorer
      apiBase="/tiktok-feeds"
      title="TikTok Explorer"
      subtitle="Monitorea palabras clave, hashtags y creadores de TikTok"
      HeaderIcon={Music2}
      itemNoun="videos"
      feedTypes={FEED_TYPES}
      theme={THEME}
    />
  )
}
