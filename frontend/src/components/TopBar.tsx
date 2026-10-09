import { useState } from 'react'
import { Link, useNavigate } from 'react-router'
import { Check, Settings, Siren, UserRound } from 'lucide-react'
import { useProfiles } from '../api/queries'
import type { ProfileListItem } from '../api/types'
import { useLock } from '../features/lock/useLock'
import { useT } from '../i18n'
import { Button } from './Button'
import { Sheet } from './Sheet'

function Avatar({ p, size = 40 }: { p?: ProfileListItem; size?: number }) {
  const initial = (p?.nickname ?? p?.full_name ?? '?').trim().charAt(0).toUpperCase()
  return p?.photo_url
    ? <img className="avatar" src={p.photo_url} alt="" width={size} height={size} />
    : <span className="avatar avatar--initial" aria-hidden="true" style={{ width: size, height: size }}>{initial}</span>
}

/** Header: profile switcher, the red Emergency button and Settings. A row of the shell, never sticky. */
export function TopBar() {
  const t = useT()
  const navigate = useNavigate()
  const { profileId, lock } = useLock()
  const profiles = useProfiles()
  const [open, setOpen] = useState(false)
  const me = profiles.data?.find(p => p.id === profileId)
  const name = me ? (me.nickname ?? me.full_name) : ''

  const switchTo = async (id: number) => {
    setOpen(false)
    if (id === profileId) return
    await lock().catch(() => {}) // the session is forgotten locally either way
    navigate(`/lock?profile=${id}`)
  }

  return (
    <header className="topbar">
      <button type="button" className="topbar__profile" onClick={() => setOpen(true)} aria-haspopup="dialog"
        aria-label={name ? `${name}, ${t('common.switchProfile')}` : t('common.switchProfile')}>
        <Avatar p={me} />
        <span className="topbar__name">{name}</span>
      </button>

      <Link to={`/emergency/${profileId}`} className="topbar__sos">
        <Siren aria-hidden="true" strokeWidth={2} />
        <span>{t('emergency.button')}</span>
      </Link>

      <Link to="/settings" className="topbar__iconlink">
        <Settings aria-hidden="true" strokeWidth={2} />
        <span>{t('nav.settings')}</span>
      </Link>

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
