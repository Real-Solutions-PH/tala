// The lock screen's "Buksan gamit ang Face ID / fingerprint" button. Self-contained so the lock screen only
// mounts it: it renders nothing unless this device has a user-verifying platform authenticator AND the
// profile has a biometric enrolled (GET /api/profiles -> has_biometric).
import { useEffect, useState } from 'react'
import { Fingerprint, ScanFace } from 'lucide-react'
import { ApiError } from '../../api/client'
import { Button } from '../../components/Button'
import { useToast } from '../../components/Toast'
import { useT, type Key } from '../../i18n'
import { useLock } from './useLock'
import { biometricAvailable, unlockWithBiometric } from './webauthn'
import './biometric.css'

type Props = { profileId: number; hasBiometric: boolean; onUnlocked: () => void; disabled?: boolean; asKey?: boolean }

const KNOWN: ReadonlySet<string> = new Set(['lock.biometricNeedsDomain', 'settings.biometricNotSet', 'settings.biometricFailed'])

/** `asKey`: the prototype's Face ID key in the keypad's empty corner; a failure shows as a toast there. */
export function BiometricUnlock({ profileId, hasBiometric, onUnlocked, disabled = false, asKey = false }: Props) {
  const toast = useToast()
  const t = useT()
  const { adopt } = useLock()
  const [available, setAvailable] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<{ pid: number; key: Key } | null>(null) // tied to the profile it was for

  useEffect(() => {
    let live = true
    biometricAvailable().then(ok => { if (live) setAvailable(ok) })
    return () => { live = false }
  }, [])

  if (!available || !hasBiometric) return null

  const go = async () => {
    setBusy(true)
    setError(null)
    try {
      await unlockWithBiometric(profileId)
      adopt(profileId)
      onUnlocked()
    } catch (e) {
      const detail = e instanceof ApiError ? e.detail : null
      const key: Key = detail && KNOWN.has(detail) ? detail as Key : 'settings.biometricFailed'
      if (asKey) toast(t(key), 'error')
      else setError({ pid: profileId, key })
    } finally {
      setBusy(false)
    }
  }

  if (asKey) {
    return (
      <button type="button" className="key key--plain" onClick={go} disabled={disabled || busy} aria-busy={busy || undefined}
        aria-label={t('lock.faceId')}>
        <ScanFace aria-hidden="true" strokeWidth={2} />
      </button>
    )
  }

  return (
    <div className="biometric-unlock">
      <Button variant="secondary" size="lg" block icon={Fingerprint} loading={busy} disabled={disabled} onClick={go}>
        {t('settings.biometricButton')}
      </Button>
      {error?.pid === profileId && <p className="biometric-unlock__error" role="alert">{t(error.key)}</p>}
    </div>
  )
}
