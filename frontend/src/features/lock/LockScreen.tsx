// The lock screen: pick whose record, enter the 6-digit PIN. The red Emergency button reaches the public
// emergency card without unlocking (spec section 3). Biometric unlock sits under the pad.
import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router'
import { Delete, Lock, Siren } from 'lucide-react'
import { ApiError } from '../../api/client'
import { useProfiles } from '../../api/queries'
import type { ProfileListItem } from '../../api/types'
import { ErrorState } from '../../components/ErrorState'
import { Skeleton } from '../../components/Skeleton'
import { useT } from '../../i18n'
import { BiometricUnlock } from './BiometricUnlock'
import { errorKey } from './errorKey'
import { useLock } from './useLock'
import './lock.css'

const PIN_LEN = 6
const DEFAULT_BACKOFF = 60 // seconds; matches the backend's BACKOFF when no Retry-After arrives
const KEYS = ['1', '2', '3', '4', '5', '6', '7', '8', '9']

function Avatar({ p }: { p: ProfileListItem }) {
  const initial = (p.nickname ?? p.full_name).trim().charAt(0).toUpperCase()
  return p.photo_url
    ? <img className="lock-avatar__img" src={p.photo_url} alt="" />
    : <span className="lock-avatar__img lock-avatar__img--initial" aria-hidden="true">{initial}</span>
}

export function LockScreen() {
  const t = useT()
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const { unlock } = useLock()
  const profiles = useProfiles()

  const wanted = Number(params.get('profile')) || null
  const [chosen, setChosen] = useState<number | null>(null)
  const list = profiles.data ?? []
  const selected = list.find(p => p.id === chosen)?.id ?? list.find(p => p.id === wanted)?.id ?? list[0]?.id ?? null

  const [pin, setPin] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<'wrong' | 'other' | null>(null)
  const [otherKey, setOtherKey] = useState<ReturnType<typeof errorKey>>('errors.generic')
  const [shake, setShake] = useState(0)
  const [waitUntil, setWaitUntil] = useState<number | null>(null)
  const [now, setNow] = useState(() => Date.now())
  const submitting = useRef(false)

  const secondsLeft = waitUntil == null ? 0 : Math.max(0, Math.ceil((waitUntil - now) / 1000))
  const blocked = secondsLeft > 0

  useEffect(() => {
    if (waitUntil == null) return
    const id = setInterval(() => {
      const n = Date.now()
      setNow(n)
      if (n >= waitUntil) { setWaitUntil(null); setError(null) }
    }, 1000)
    return () => clearInterval(id)
  }, [waitUntil])

  const submit = useCallback(async (pid: number, value: string) => {
    if (submitting.current) return
    submitting.current = true
    setBusy(true)
    try {
      await unlock(pid, value)
      navigate('/chat', { replace: true })
    } catch (err) {
      setPin('')
      if (err instanceof ApiError && err.status === 429) {
        const n = Date.now()
        setNow(n)
        setWaitUntil(n + (err.retryAfter ?? DEFAULT_BACKOFF) * 1000)
        setError(null)
      } else if (err instanceof ApiError && err.status === 401) {
        setError('wrong')
        setShake(s => s + 1)
      } else {
        setOtherKey(errorKey(err))
        setError('other')
      }
    } finally {
      submitting.current = false
      setBusy(false)
    }
  }, [unlock, navigate])

  const press = useCallback((d: string) => {
    if (selected == null || blocked || busy) return
    setError(null)
    if (pin.length >= PIN_LEN) return
    const next = pin + d
    setPin(next)
    if (next.length === PIN_LEN) void submit(selected, next) // the 6th digit submits; no Unlock button to find
  }, [selected, blocked, busy, pin, submit])

  const backspace = useCallback(() => setPin(p => p.slice(0, -1)), [])

  // A hardware keyboard works too (laptop demo, Bluetooth keyboards).
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.metaKey || e.ctrlKey || e.altKey) return
      if (/^\d$/.test(e.key)) press(e.key)
      else if (e.key === 'Backspace') backspace()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [press, backspace])

  const choose = (id: number) => { setChosen(id); setPin(''); setError(null) }
  const keysDisabled = selected == null || blocked || busy

  return (
    <main className="standalone lock">
      <div className="lock__inner">
        {selected != null ? (
          <Link to={`/emergency/${selected}`} className="lock__sos">
            <Siren aria-hidden="true" strokeWidth={2} />
            <span>{t('emergency.button')}</span>
          </Link>
        ) : (
          <button type="button" className="lock__sos" disabled>
            <Siren aria-hidden="true" strokeWidth={2} />
            <span>{t('emergency.button')}</span>
          </button>
        )}

        <h1 className="lock__title"><Lock aria-hidden="true" strokeWidth={2} /><span>{t('lock.title')}</span></h1>

        {profiles.isPending ? (
          <div className="lock__profiles" aria-busy="true">
            <Skeleton width={88} height={112} radius={20} />
            <Skeleton width={88} height={112} radius={20} />
          </div>
        ) : profiles.isError ? (
          <ErrorState message={errorKey(profiles.error)} onRetry={() => { profiles.refetch() }} />
        ) : (
          <div className="lock__profiles" role="radiogroup" aria-label={t('lock.whoIs')}>
            {list.map(p => (
              <button key={p.id} type="button" role="radio" aria-checked={p.id === selected} className="lock-avatar"
                onClick={() => choose(p.id)}>
                <Avatar p={p} />
                <span className="lock-avatar__name">{p.nickname ?? p.full_name}</span>
              </button>
            ))}
          </div>
        )}

        <p className="lock__prompt" id="pin-label">{t('lock.enterPin')}</p>

        <div key={shake} className={['pin-dots', shake > 0 && error === 'wrong' && 'pin-dots--shake'].filter(Boolean).join(' ')}
          role="img" aria-labelledby="pin-label pin-progress">
          {Array.from({ length: PIN_LEN }, (_, i) => (
            <span key={i} className={['pin-dot', i < pin.length && 'pin-dot--on'].filter(Boolean).join(' ')} />
          ))}
        </div>
        <span id="pin-progress" className="sr-only">{t('lock.pinProgress', { n: pin.length })}</span>

        <div className="lock__status" role="status" aria-live="polite">
          {busy && <p className="lock__msg">{t('lock.checking')}</p>}
          {error === 'wrong' && <p className="lock__msg lock__msg--error">{t('errors.wrongPin')}</p>}
          {error === 'other' && <p className="lock__msg lock__msg--error">{t(otherKey)}</p>}
          {blocked && (
            <div className="lock__msg lock__msg--error">
              <p>{t('errors.tooManyAttempts')}</p>
              <p className="lock__countdown">{t('lock.tryAgainIn', { n: secondsLeft })}</p>
            </div>
          )}
        </div>

        <div className="pinpad">
          {KEYS.map(d => (
            <button key={d} type="button" className="pinpad__key" onClick={() => press(d)} disabled={keysDisabled}>{d}</button>
          ))}
          <span aria-hidden="true" />
          <button type="button" className="pinpad__key" onClick={() => press('0')} disabled={keysDisabled}>0</button>
          <button type="button" className="pinpad__key pinpad__key--del" onClick={backspace} disabled={keysDisabled}
            aria-label={t('lock.deleteDigit')}>
            <Delete aria-hidden="true" strokeWidth={2} />
            <span aria-hidden="true">{t('common.delete')}</span>
          </button>
        </div>

        {selected != null && (
          <BiometricUnlock key={selected} profileId={selected} hasBiometric={list.find(p => p.id === selected)?.has_biometric ?? false}
            disabled={blocked || busy} onUnlocked={() => navigate('/chat', { replace: true })} />
        )}
      </div>
    </main>
  )
}
