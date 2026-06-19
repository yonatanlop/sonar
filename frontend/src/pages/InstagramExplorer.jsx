/**
 * Instagram Explorer — monitores por hashtag o cuenta/usuario.
 */
import { Instagram, Hash, User } from 'lucide-react'
import PlatformExplorer from '../components/PlatformExplorer'

const THEME = {
  iconBg: 'bg-pink-100', iconText: 'text-pink-600',
  addBtn: 'bg-pink-600 hover:bg-pink-700',
  selectedBg: 'bg-pink-50 border-pink-200',
  selectedIconBg: 'bg-pink-100', selectedIconText: 'text-pink-600',
  chevron: 'text-pink-400',
  linkHover: 'hover:text-pink-600',
  spinner: 'text-pink-400',
  ring: 'focus:ring-pink-400',
  modalBtn: 'bg-pink-600 hover:bg-pink-700',
  modalTypeActive: 'bg-pink-50 border-pink-400 text-pink-700',
}

const FEED_TYPES = [
  { value: 'hashtag', icon: Hash, label: 'Hashtag', groupLabel: 'Hashtags', placeholder: 'mira (sin #)' },
  { value: 'account', icon: User, label: 'Cuenta',  groupLabel: 'Cuentas',  placeholder: 'usuario (sin @)' },
]

export default function InstagramExplorer() {
  return (
    <PlatformExplorer
      apiBase="/instagram-feeds"
      title="Instagram Explorer"
      subtitle="Monitorea hashtags y cuentas de Instagram"
      HeaderIcon={Instagram}
      itemNoun="publicaciones"
      feedTypes={FEED_TYPES}
      theme={THEME}
    />
  )
}
