import { useLayoutEffect, useRef } from 'react'
import { NavLink } from 'react-router'
import { FileHeart, House, Mic, Pill, WalletCards, type LucideIcon } from 'lucide-react'
import { useT, type Key } from '../i18n'

const ITEMS: { to: string; label: Key; icon: LucideIcon }[] = [
  { to: '/home', label: 'nav.home', icon: House },
  { to: '/records', label: 'nav.records', icon: FileHeart },
  { to: '/cards', label: 'nav.cards', icon: WalletCards },
  { to: '/meds', label: 'nav.meds', icon: Pill },
]

/**
 * The bottom menu, after the prototype's dock: a white pill of four tabs (icon above a word) and, beside it,
 * the round blue Kausap button. The current one is marked aria-current="page".
 * It is the last row of the shell grid (never fixed). Its measured height is published as --nav-h on
 * <html> so toasts sit just above it, whatever the text size.
 */
export function BottomNav() {
  const t = useT()
  const ref = useRef<HTMLElement>(null)

  useLayoutEffect(() => {
    const el = ref.current
    if (!el) return
    const root = document.documentElement.style
    const publish = (h: number) => root.setProperty('--nav-h', `${Math.round(h)}px`)
    publish(el.getBoundingClientRect().height)
    if (typeof ResizeObserver === 'undefined') return () => root.removeProperty('--nav-h')
    const ro = new ResizeObserver(entries => {
      const e = entries[0]
      publish(e.borderBoxSize?.[0]?.blockSize ?? e.target.getBoundingClientRect().height)
    })
    ro.observe(el)
    return () => { ro.disconnect(); root.removeProperty('--nav-h') }
  }, [])

  return (
    <nav ref={ref} className="bottomnav" aria-label={t('nav.label')}>
      <div className="bottomnav__tabs">
        {ITEMS.map(({ to, label, icon: Icon }) => (
          <NavLink key={to} to={to} className="navitem">
            <span className="navitem__icon"><Icon aria-hidden="true" strokeWidth={2} /></span>
            <span className="navitem__label">{t(label)}</span>
          </NavLink>
        ))}
      </div>
      <NavLink to="/chat" className="navitem navitem--ask">
        <span className="navitem__icon"><Mic aria-hidden="true" strokeWidth={2} /></span>
        <span className="navitem__label">{t('nav.chat')}</span>
      </NavLink>
    </nav>
  )
}
