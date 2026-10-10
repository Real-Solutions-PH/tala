import { useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router'
import { ArrowLeft, Check, Settings, UserRound } from 'lucide-react'
import { useProfiles } from '../api/queries'
import type { ProfileListItem } from '../api/types'
import { useLock } from '../features/lock/useLock'
import { useT, type Key } from '../i18n'
import { BackLink } from './BackLink'
import { Button } from './Button'
import { Sheet } from './Sheet'

function Avatar({ p, size = 40 }: { p?: ProfileListItem; size?: number }) {
  const initial = (p?.nickname ?? p?.full_name ?? '?').trim().charAt(0).toUpperCase()
  return p?.photo_url
    ? <img className="avatar" src={p.photo_url} alt="" width={size} height={size} />
    : <span className="avatar avatar--initial" aria-hidden="true" style={{ width: size, height: size }}>{initial}</span>
}

/** Screen name in the title bar, by the first path segment. */
const TITLES: Record<string, Key> = {
  chat: 'nav.chat', usap: 'nav.chat', cards: 'nav.cards', meds: 'nav.meds', records: 'nav.records',
  settings: 'nav.settings', profile: 'common.profile',
}
/** Tab screens go back to Home; deeper screens go back one step, or to their parent when opened directly. */
const TABS = new Set(['/chat', '/usap', '/cards', '/meds', '/records'])
function parentOf(path: string): string {
  if (path === '/profile') return '/settings'
  const seg = path.split('/')[1]
  return seg === 'settings' ? '/home' : `/${seg}`
}

/**
 * Header, after the prototype. On Home: the person (opens the profile switcher) with a greeting, and Settings.
 * Elsewhere: a title bar with a round back button, the screen name and the person's avatar. A row of the shell,
 * never sticky.
 */
export function TopBar() {
  const t = useT()
  const navigate = useNavigate()
  const { pathname } = useLocation()
  const { profileId, lock } = useLock()
  const profiles = useProfiles()
  const [open, setOpen] = useState(false)
  const me = profiles.data?.find(p => p.id === profileId)
  const name = me ? (me.nickname ?? me.full_name) : ''
  const home = pathname === '/home'
  const title = TITLES[pathname.split('/')[1]]

  const switchTo = async (id: number) => {
    setOpen(false)
    if (id === profileId) return
    await lock().catch(() => {}) // the session is forgotten locally either way
    navigate(`/lock?profile=${id}`)
  }

  const profileLabel = name ? `${name}, ${t('common.switchProfile')}` : t('common.switchProfile')

  return (
    <header className={home ? 'topbar topbar--home' : 'topbar topbar--title'}>
      {home ? (
        <>
          <button type="button" className="topbar__hello" onClick={() => setOpen(true)} aria-haspopup="dialog" aria-label={profileLabel}>
            <Avatar p={me} size={52} />
            <span className="topbar__who" aria-hidden="true">
              <span className="topbar__greet">{t('home.hello')}</span>
              <span className="topbar__name">{name}</span>
            </span>
          </button>
          <Link to="/settings" className="topbar__iconlink" title={t('nav.settings')}>
            <Settings aria-hidden="true" strokeWidth={2} />
            <span className="sr-only">{t('nav.settings')}</span>
          </Link>
        </>
      ) : (
        <>
          {TABS.has(pathname)
            ? <Link to="/home" className="back-link" title={t('common.back')}><ArrowLeft aria-hidden="true" /><span className="sr-only">{t('common.back')}</span></Link>
            : <BackLink fallback={parentOf(pathname)} />}
          <p className="topbar__title">{title ? t(title) : ''}</p>
          <button type="button" className="topbar__profile" onClick={() => setOpen(true)} aria-haspopup="dialog" aria-label={profileLabel}>
            <Avatar p={me} size={48} />
          </button>
        </>
      )}

      <Sheet open={open} onClose={() => setOpen(false)} title={t('common.switchProfile')}>
        {open && <ul className="profile-list">
          {profiles.data?.map(p => (
            <li key={p.id}>
              <button type="button" className="profile-list__item" onClick={() => switchTo(p.id)} aria-current={p.id === profileId || undefined}>
                <Avatar p={p} size={48} />
                <span className="profile-list__name">{p.nickname ?? p.full_name}</span>
                {p.id === profileId && <Check aria-hidden="true" />}
              </button>
            </li>
          ))}
        </ul>}
        <Button variant="secondary" block icon={UserRound} onClick={() => { setOpen(false); navigate('/profile') }}>{t('common.profile')}</Button>
      </Sheet>
    </header>
  )
}
