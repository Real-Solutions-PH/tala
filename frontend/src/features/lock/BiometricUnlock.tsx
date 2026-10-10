// The lock screen's "Buksan gamit ang Face ID / fingerprint" button. Self-contained so the lock screen only
// mounts it: it renders nothing unless this device has a user-verifying platform authenticator AND the
// profile has a biometric enrolled (GET /api/profiles -> has_biometric).
import { useEffect, useState } from 'react'
import { Fingerprint } from 'lucide-react'
import { ApiError } from '../../api/client'
import { Button } from '../../components/Button'
import { useT, type Key } from '../../i18n'
import { useLock } from './useLock'
import { biometricAvailable, unlockWithBiometric } from './webauthn'
import './biometric.css'

type Props = { profileId: number; hasBiometric: boolean; onUnlocked: () => void; disabled?: boolean }

const KNOWN: ReadonlySet<string> = new Set(['lock.biometricNeedsDomain', 'settings.biometricNotSet', 'settings.biometricFailed'])

export function BiometricUnlock({ profileId, hasBiometric, onUnlocked, disabled = false }: Props) {
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
      setError({ pid: profileId, key: detail && KNOWN.has(detail) ? detail as Key : 'settings.biometricFailed' })
    } finally {
      setBusy(false)
    }
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
