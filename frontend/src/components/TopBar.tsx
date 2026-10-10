import { useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router'
import { ChevronLeft, Lock, Plane, Settings, TriangleAlert, UserRound, type LucideIcon } from 'lucide-react'
import { useProfiles } from '../api/queries'
import type { ProfileListItem } from '../api/types'
import { useLock } from '../features/lock/useLock'
import { useT, type Key } from '../i18n'
import { Button } from './Button'
import { Sheet } from './Sheet'

/** The prototype's avatar: initials (first and last name) on a blue circle. */
export function Initials({ p, size = 44 }: { p?: ProfileListItem; size?: number }) {
  const words = (p?.full_name ?? '?').trim().split(/\s+/)
  const ini = (words[0][0] + (words.length > 1 ? words[words.length - 1][0] : '')).toUpperCase()
  return <span className="av" aria-hidden="true" style={{ width: size, height: size }}>{ini}</span>
}

/** Screen name in the title bar, by the first path segment (Ask shows "Kapiling", as in the prototype). */
const TITLES: Record<string, Key> = {
  usap: 'common.appName', chat: 'common.appName', cards: 'nav.cards', meds: 'nav.meds', records: 'nav.records',
  settings: 'nav.settings', profile: 'common.profile',
}
/** Tab screens go back to Home; deeper screens go back one step, or to their parent when opened directly. */
const TABS = new Set(['/chat', '/usap', '/cards', '/meds', '/records', '/settings'])
function parentOf(path: string): string {
  if (path === '/profile') return '/settings'
  return `/${path.split('/')[1]}`
}

const TRUST: { icon: LucideIcon; title: Key; body: Key }[] = [
  { icon: Lock, title: 'home.trust1', body: 'home.trust1Body' },
  { icon: Plane, title: 'home.trust2', body: 'home.trust2Body' },
  { icon: UserRound, title: 'home.trust3', body: 'home.trust3Body' },
  { icon: TriangleAlert, title: 'home.trust4', body: 'home.trust4Body' },
]

function greeting(): Key {
  const h = new Date().getHours()
  return h < 12 ? 'home.morning' : h < 18 ? 'home.afternoon' : 'home.evening'
}

/**
 * Header, after the prototype. Home: the person ("Hi, …" and a greeting; opens "Whose record?"), the Private
 * pill and Settings. Elsewhere: a title bar with a round back button, the screen name and the person's avatar.
 * A row of the shell, never sticky.
 */
export function TopBar() {
  const t = useT()
  const navigate = useNavigate()
  const { pathname, key } = useLocation()
  const { profileId, lock } = useLock()
  const profiles = useProfiles()
  const [open, setOpen] = useState(false)
  const [trust, setTrust] = useState(false)
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
  const back = () => {
    if (TABS.has(pathname)) navigate('/home')
    else if (key !== 'default') navigate(-1)
    else navigate(parentOf(pathname))
  }
  const profileLabel = name ? `${name}, ${t('common.switchProfile')}` : t('common.switchProfile')

  return (
    <header className={home ? 'topbar topbar--home' : 'topbar topbar--title'}>
      {home ? (
        <>
          <button type="button" className="hello" onClick={() => setOpen(true)} aria-haspopup="dialog" aria-label={profileLabel}>
            <Initials p={me} size={46} />
            <span className="hello__text" aria-hidden="true">
              <b>{t('home.hello', { name })}</b>
              <span>{t(greeting())}</span>
            </span>
          </button>
          <button type="button" className="trust" onClick={() => setTrust(true)} aria-haspopup="dialog">
            <Lock aria-hidden="true" strokeWidth={2.4} /><span>{t('home.private')}</span>
          </button>
          <Link to="/settings" className="iconbtn" title={t('nav.settings')}>
            <Settings aria-hidden="true" strokeWidth={2} />
            <span className="sr-only">{t('nav.settings')}</span>
          </Link>
        </>
      ) : (
        <>
          <button type="button" className="iconbtn" onClick={back}>
            <ChevronLeft aria-hidden="true" strokeWidth={2} /><span className="sr-only">{t('common.back')}</span>
          </button>
          <p className="topbar__title">{title ? t(title) : ''}</p>
          <button type="button" className="iconbtn iconbtn--av" onClick={() => setOpen(true)} aria-haspopup="dialog" aria-label={profileLabel}>
            <Initials p={me} size={44} />
          </button>
        </>
      )}

      <Sheet open={open} onClose={() => setOpen(false)} title={t('common.whoseRecord')}>
        {open && <div className="plist">
          {profiles.data?.map(p => (
            <button key={p.id} type="button" className="pbtn" onClick={() => switchTo(p.id)} aria-pressed={p.id === profileId}>
              <Initials p={p} size={40} />
              <span className="pbtn__l"><b>{p.full_name}</b>{p.id === profileId && <span>{t('common.owner')}</span>}</span>
            </button>
          ))}
        </div>}
        <p className="sheet__note">{t('common.separateRecords')}</p>
        <Button variant="secondary" block icon={UserRound} onClick={() => { setOpen(false); navigate('/profile') }}>{t('common.profile')}</Button>
      </Sheet>

      <Sheet open={trust} onClose={() => setTrust(false)} title={t('home.trustTitle')}>
        <ul className="card trust-list">
          {TRUST.map(({ icon: Icon, title: tt, body }) => (
            <li key={tt}><Icon aria-hidden="true" strokeWidth={2} /><span><b>{t(tt)}</b><span>{t(body)}</span></span></li>
          ))}
        </ul>
        <Button size="lg" block onClick={() => setTrust(false)}>{t('home.gotIt')}</Button>
      </Sheet>
    </header>
  )
}
