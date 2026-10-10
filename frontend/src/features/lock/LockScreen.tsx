// The lock screen: pick whose record, enter the 6-digit PIN. The red Emergency button reaches the public
// emergency card without unlocking (spec section 3). Biometric unlock sits under the pad.
import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router'
import { Delete, HeartPulse } from 'lucide-react'
import { ApiError } from '../../api/client'
import { useProfiles } from '../../api/queries'
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
      navigate('/home', { replace: true })
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
        <KapilingLogo />
        <h1 className="lock__title">{t('common.appName')}</h1>
        <p className="sub" id="pin-label">{t('lock.enterPin')}</p>

        {profiles.isPending ? <Skeleton width={180} height={38} radius={999} />
          : profiles.isError ? <ErrorState message={errorKey(profiles.error)} onRetry={() => { profiles.refetch() }} />
          : list.length > 1 && (
            <div className="seg lock__who" role="radiogroup" aria-label={t('lock.whoIs')}>
              {list.map(p => (
                <button key={p.id} type="button" role="radio" aria-checked={p.id === selected} aria-pressed={p.id === selected}
                  onClick={() => choose(p.id)}>{p.nickname ?? p.full_name}</button>
              ))}
            </div>
          )}

        <div key={shake} className={['dots', shake > 0 && error === 'wrong' && 'dots--shake'].filter(Boolean).join(' ')}
          role="img" aria-labelledby="pin-label pin-progress">
          {Array.from({ length: PIN_LEN }, (_, i) => <i key={i} className={i < pin.length ? 'f' : undefined} />)}
        </div>
        <span id="pin-progress" className="sr-only">{t('lock.pinProgress', { n: pin.length })}</span>

        <div className="pinmsg" role="status" aria-live="polite">
          {busy && <p>{t('lock.checking')}</p>}
          {error === 'wrong' && <p className="err">{t('errors.wrongPin')}</p>}
          {error === 'other' && <p className="err">{t(otherKey)}</p>}
          {blocked && (
            <div className="err">
              <p>{t('errors.tooManyAttempts')}</p>
              <p className="lock__countdown">{t('lock.tryAgainIn', { n: secondsLeft })}</p>
            </div>
          )}
        </div>

        <div className="pad">
          {KEYS.map(d => (
            <button key={d} type="button" className="key" onClick={() => press(d)} disabled={keysDisabled}>{d}</button>
          ))}
          <span className="pad__slot">
            {selected != null && (
              <BiometricUnlock key={selected} asKey profileId={selected} hasBiometric={list.find(p => p.id === selected)?.has_biometric ?? false}
                disabled={blocked || busy} onUnlocked={() => navigate('/home', { replace: true })} />
            )}
          </span>
          <button type="button" className="key" onClick={() => press('0')} disabled={keysDisabled}>0</button>
          <button type="button" className="key key--plain" onClick={backspace} disabled={keysDisabled} aria-label={t('lock.deleteDigit')}>
            <Delete aria-hidden="true" strokeWidth={2} />
          </button>
        </div>

        {selected != null ? (
          <Link to={`/emergency/${selected}`} className="emerg"><HeartPulse aria-hidden="true" strokeWidth={2} /><span>{t('lock.emergencyNoUnlock')}</span></Link>
        ) : (
          <button type="button" className="emerg" disabled><HeartPulse aria-hidden="true" strokeWidth={2} /><span>{t('lock.emergencyNoUnlock')}</span></button>
        )}
      </div>
    </main>
  )
}

/** The prototype's mark: a blue rounded square with two hearts' worth of curve and two dots (people side by side). */
function KapilingLogo() {
  return (
    <svg className="lock__logo" viewBox="0 0 32 32" aria-hidden="true">
      <rect width="32" height="32" rx="9" fill="var(--primary-fill)" />
      <path d="M11 22c-2.5-1.7-4-4.2-4-7a5 5 0 0 1 9-3 5 5 0 0 1 9 3c0 2.8-1.5 5.3-4 7" fill="none" stroke="var(--on-primary)" strokeWidth="2.4" strokeLinecap="round" />
      <circle cx="12.5" cy="23.5" r="2.3" fill="var(--on-primary)" />
      <circle cx="19.5" cy="23.5" r="2.3" fill="var(--on-primary)" />
    </svg>
  )
}
