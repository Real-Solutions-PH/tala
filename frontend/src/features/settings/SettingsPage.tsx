// Settings (Task 15): language, text size, emergency card fields, representatives, PIN, biometric unlock,
// the access log, lock now and what runs on this device. Owner-only controls are hidden for a representative
// and refused by the server anyway (403 settings.ownerOnly).
import { useEffect, useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router'
import { useQueryClient } from '@tanstack/react-query'
import {
  ALargeSmall, FingerprintPattern, Palette, IdCard, Info, KeyRound, Languages, Lock, ScrollText, ShieldCheck,
  UserPlus, UserRound, Users,
} from 'lucide-react'
import { api } from '../../api/client'
import { keys } from '../../api/queries'
import { Button } from '../../components/Button'
import { ErrorState } from '../../components/ErrorState'
import { Sheet } from '../../components/Sheet'
import { Skeleton } from '../../components/Skeleton'
import { useToast } from '../../components/Toast'
import { translate, useLang, useT, type Key, type Lang } from '../../i18n'
import { useLock } from '../lock/useLock'
import { biometricAvailable, enrolBiometric } from '../lock/webauthn'
import { AccessLog } from './AccessLog'
import { EMERGENCY_FIELDS, settingsKeys, useSettingsInfo, type Representative, type SettingsInfo } from './api'
import { ConfirmSheet } from './ConfirmSheet'
import { errorKey } from './errorKey'
import { Field, FormError, Section } from './parts'
import { applyTextScale, readTextScale, SCALES, type Scale } from './textScale'
import { applyTheme, readTheme, THEMES, type Theme } from './theme'
import './settings.css'
import { DisplayTitle } from '../../components/DisplayTitle'

const SCALE_LABEL: Record<Scale, Key> = { 1: 'settings.textNormal', 1.25: 'settings.textLarge', 1.5: 'settings.textLarger' }

function OwnerOnlyNote() {
  const t = useT()
  return <p className="settings-note"><ShieldCheck aria-hidden="true" /><span>{t('settings.ownerOnly')}</span></p>
}

// --- language and text size ---------------------------------------------------------------

function LanguageSection({ profileId }: { profileId: number | null }) {
  const t = useT()
  const [lang, setLang] = useLang()
  const toast = useToast()
  const qc = useQueryClient()
  const choose = async (l: Lang) => {
    if (l === lang) return
    setLang(l) // applies at once; the profile copy follows
    try {
      await api.send('PUT', `/profiles/${profileId}`, { language: l })
      qc.invalidateQueries({ queryKey: settingsKeys.profile(profileId) })
      toast(translate(l, 'toasts.languageChanged'))
    } catch {
      toast(translate(l, 'toasts.failed'), 'error')
    }
  }
  return (
    <Section icon={Languages} title={t('settings.language')}>
      <div className="choice-row">
        {(['en', 'tl'] as const).map(l => (
          <button key={l} type="button" className="choice" aria-pressed={lang === l} onClick={() => choose(l)} lang={l === 'tl' ? 'fil' : 'en'}>
            {l === 'en' ? t('common.english') : t('common.tagalog')}
          </button>
        ))}
      </div>
    </Section>
  )
}

function TextSizeSection() {
  const t = useT()
  const toast = useToast()
  const [scale, setScale] = useState<Scale>(readTextScale)
  const choose = (s: Scale) => {
    applyTextScale(s)
    setScale(s)
    toast(t('settings.textSizeChanged'))
  }
  return (
    <Section icon={ALargeSmall} title={t('settings.textSize')}>
      <div className="choice-row choice-row--stack">
        {SCALES.map(s => (
          // The sample is sized relative to the current scale so each row previews its own size.
          <button key={s} type="button" className="choice" aria-pressed={scale === s} onClick={() => choose(s)}>
            <span>{Math.round(s * 100)}%</span>
            <span className="choice__sample" style={{ fontSize: `calc(var(--fs-body) * ${s} / var(--text-scale))` }}>{t(SCALE_LABEL[s])}</span>
          </button>
        ))}
      </div>
      <p className="text-preview">{t('settings.textPreview')}</p>
    </Section>
  )
}

// --- theme -------------------------------------------------------------------------------------------------

const THEME_LABEL: Record<Theme, Key> = { blue: 'settings.themeBlue', mint: 'settings.themeMint', navy: 'settings.themeNavy', contrast: 'settings.themeContrast' }

/** Four looks from the prototype. Each button shows its two colours (data-skin on the swatch) and its name. */
function ThemeSection() {
  const t = useT()
  const [theme, setTheme] = useState<Theme>(readTheme)
  const choose = (th: Theme) => { applyTheme(th); setTheme(th) }
  return (
    <Section icon={Palette} title={t('settings.theme')}>
      <div className="skins">
        {THEMES.map(th => (
          <button key={th} type="button" className="skin" aria-pressed={theme === th} onClick={() => choose(th)}>
            <span className="skin__sw" data-skin={th} aria-hidden="true"><i /><i /></span>
            <span>{t(THEME_LABEL[th])}</span>
          </button>
        ))}
      </div>
    </Section>
  )
}

// --- emergency card fields ---------------------------------------------------------------------

function EmergencyFieldsSection({ profileId, info }: { profileId: number | null; info: SettingsInfo }) {
  const t = useT()
  const toast = useToast()
  const qc = useQueryClient()
  const [fields, setFields] = useState<string[]>(info.emergency_fields)

  const toggle = async (f: string, on: boolean) => {
    const before = fields
    const next = EMERGENCY_FIELDS.filter(x => (x === f ? on : fields.includes(x)))
    setFields(next)
    try {
      await api.send('PUT', `/profiles/${profileId}/emergency-fields`, { fields: next })
      qc.setQueryData<SettingsInfo>(settingsKeys.settings(profileId), d => d && { ...d, emergency_fields: next })
      qc.invalidateQueries({ queryKey: keys.emergency(profileId) })
      toast(t('toasts.saved'))
    } catch (e) {
      setFields(before)
      toast(t(errorKey(e)), 'error')
    }
  }

  return (
    <Section icon={IdCard} title={t('settings.emergencyFields')} hint={t('settings.emergencyFieldsHint')}>
      <ul className="toggle-list">
        {EMERGENCY_FIELDS.map(f => (
          <li key={f}>
            <label className="toggle">
              <span>{t(`fields.${f}` as Key)}</span>
              <input type="checkbox" role="switch" checked={fields.includes(f)} onChange={e => toggle(f, e.target.checked)} />
            </label>
          </li>
        ))}
      </ul>
    </Section>
  )
}

// --- representatives ------------------------------------------------------------------------------

const SIX = /^[0-9]{6}$/

function AddRepresentativeForm({ profileId, onDone }: { profileId: number | null; onDone: () => void }) {
  const t = useT()
  const toast = useToast()
  const qc = useQueryClient()
  const [name, setName] = useState('')
  const [relation, setRelation] = useState('')
  const [pin, setPin] = useState('')
  const [error, setError] = useState<Key | null>(null)
  const [busy, setBusy] = useState(false)

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    if (!name.trim()) return setError('profile.required')
    if (!SIX.test(pin)) return setError('settings.pinSixDigits')
    setBusy(true)
    setError(null)
    try {
      await api.send('POST', `/profiles/${profileId}/representatives`, { name: name.trim(), relation: relation.trim() || null, pin })
      await qc.invalidateQueries({ queryKey: settingsKeys.settings(profileId) })
      toast(t('settings.repAdded', { name: name.trim() }))
      onDone()
    } catch (err) {
      setError(errorKey(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <form className="form" onSubmit={submit} noValidate>
      <Field label={t('settings.repName')}>
        {({ id }) => <input id={id} className="field__input" value={name} onChange={e => setName(e.target.value)} autoComplete="off" maxLength={80} inputMode="text" />}
      </Field>
      <Field label={t('settings.repRelation')}>
        {({ id }) => <input id={id} className="field__input" value={relation} onChange={e => setRelation(e.target.value)} autoComplete="off" maxLength={40} inputMode="text" />}
      </Field>
      <Field label={t('settings.repPin')} hint={t('settings.repPinHint')}>
        {({ id, describedBy }) => (
          <input id={id} className="field__input tabular" value={pin} aria-describedby={describedBy}
            onChange={e => setPin(e.target.value.replace(/\D/g, '').slice(0, 6))}
            inputMode="numeric" autoComplete="off" type="password" maxLength={6} aria-invalid={error === 'settings.pinInUse' || error === 'settings.pinSixDigits' || undefined} />
        )}
      </Field>
      <FormError message={error && t(error)} />
      <Button type="submit" size="lg" block icon={UserPlus} loading={busy}>{t('common.save')}</Button>
    </form>
  )
}

function RepresentativesSection({ profileId, info }: { profileId: number | null; info: SettingsInfo }) {
  const t = useT()
  const toast = useToast()
  const qc = useQueryClient()
  const [adding, setAdding] = useState(false)
  const [removing, setRemoving] = useState<Representative | null>(null)
  const [busy, setBusy] = useState(false)
  const owner = info.role === 'owner'

  const remove = async () => {
    if (!removing) return
    setBusy(true)
    try {
      await api.send('DELETE', `/profiles/${profileId}/representatives/${removing.id}`)
      qc.setQueryData<SettingsInfo>(settingsKeys.settings(profileId), d => d && { ...d, representatives: d.representatives.filter(r => r.id !== removing.id) })
      toast(t('settings.repRemoved', { name: removing.name }))
      setRemoving(null)
    } catch (e) {
      toast(t(errorKey(e)), 'error')
    } finally {
      setBusy(false)
    }
  }

  return (
    <Section icon={Users} title={t('settings.representatives')} hint={t('settings.representativesHint')}>
      {!owner ? <OwnerOnlyNote /> : (
        <>
          {info.representatives.length === 0
            ? <p className="muted">{t('settings.noRepresentatives')}</p>
            : (
              <ul className="item-list">
                {info.representatives.map(r => (
                  <li key={r.id} className="item">
                    <span className="item__text">
                      <span className="item__name">{r.name}</span>
                      {r.relation && <span className="item__sub">{r.relation}</span>}
                    </span>
                    <Button variant="ghost" onClick={() => setRemoving(r)} aria-label={`${t('settings.remove')}: ${r.name}`}>{t('settings.remove')}</Button>
                  </li>
                ))}
              </ul>
            )}
          <Button variant="secondary" size="lg" block icon={UserPlus} onClick={() => setAdding(true)}>{t('settings.addRepresentative')}</Button>
          <Sheet open={adding} onClose={() => setAdding(false)} title={t('settings.addRepresentative')}>
            {adding && <AddRepresentativeForm profileId={profileId} onDone={() => setAdding(false)} />}
          </Sheet>
          <ConfirmSheet open={removing != null} onClose={() => setRemoving(null)} busy={busy} onConfirm={remove}
            title={t('settings.removeRepTitle', { name: removing?.name ?? '' })}
            body={t('settings.removeRepBody', { name: removing?.name ?? '' })}
            confirmLabel={t('settings.removeRepConfirm')} />
        </>
      )}
    </Section>
  )
}

// --- PIN, biometric, lock -----------------------------------------------------------------------------

function ChangePinForm({ profileId, onDone }: { profileId: number | null; onDone: () => void }) {
  const t = useT()
  const toast = useToast()
  const [current, setCurrent] = useState('')
  const [next, setNext] = useState('')
  const [again, setAgain] = useState('')
  const [error, setError] = useState<Key | null>(null)
  const [busy, setBusy] = useState(false)
  const digits = (set: (v: string) => void) => (e: { target: { value: string } }) => set(e.target.value.replace(/\D/g, '').slice(0, 6))

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    if (!SIX.test(current) || !SIX.test(next)) return setError('settings.pinSixDigits')
    if (next !== again) return setError('settings.pinMismatch')
    setBusy(true)
    setError(null)
    try {
      await api.send('PUT', `/profiles/${profileId}/pin`, { current_pin: current, new_pin: next })
      toast(t('settings.pinChanged'))
      onDone()
    } catch (err) {
      setError(errorKey(err))
    } finally {
      setBusy(false)
    }
  }

  const pinInput = (value: string, onChange: (e: { target: { value: string } }) => void, autoComplete: string) =>
    ({ id }: { id: string }) => (
      <input id={id} className="field__input tabular" type="password" inputMode="numeric" maxLength={6}
        autoComplete={autoComplete} value={value} onChange={onChange} />
    )

  return (
    <form className="form" onSubmit={submit} noValidate>
      <Field label={t('settings.currentPin')}>{pinInput(current, digits(setCurrent), 'current-password')}</Field>
      <Field label={t('settings.newPin')}>{pinInput(next, digits(setNext), 'new-password')}</Field>
      <Field label={t('settings.confirmPin')}>{pinInput(again, digits(setAgain), 'new-password')}</Field>
      <FormError message={error && t(error)} />
      <Button type="submit" size="lg" block icon={KeyRound} loading={busy}>{t('settings.changePin')}</Button>
    </form>
  )
}

function EnrolBiometricForm({ onEnrol }: { onEnrol: (pin: string) => Promise<Key | null> }) {
  const t = useT()
  const [pin, setPin] = useState('')
  const [error, setError] = useState<Key | null>(null)
  const [busy, setBusy] = useState(false)
  const submit = async (e: FormEvent) => {
    e.preventDefault()
    if (!SIX.test(pin)) return setError('settings.pinSixDigits')
    setBusy(true)
    setError(await onEnrol(pin))
    setBusy(false)
  }
  return (
    <form className="form" onSubmit={submit} noValidate>
      <p>{t('settings.biometricPinPrompt')}</p>
      <Field label={t('settings.currentPin')}>
        {({ id }) => (
          <input id={id} className="field__input tabular" type="password" inputMode="numeric" maxLength={6}
            autoComplete="current-password" value={pin} onChange={e => setPin(e.target.value.replace(/\D/g, '').slice(0, 6))} />
        )}
      </Field>
      <FormError message={error && t(error)} />
      <Button type="submit" size="lg" block icon={FingerprintPattern} loading={busy}>{t('settings.biometricTurnOn')}</Button>
    </form>
  )
}

function BiometricSetting({ profileId, enabled }: { profileId: number | null; enabled: boolean }) {
  const t = useT()
  const toast = useToast()
  const qc = useQueryClient()
  const [available, setAvailable] = useState(false)
  const [busy, setBusy] = useState(false)
  const [asking, setAsking] = useState(false)
  useEffect(() => {
    let live = true
    biometricAvailable().then(ok => { if (live) setAvailable(ok) })
    return () => { live = false }
  }, [])
  if (!available) return null // shown only where this device can do it

  const refresh = () => Promise.all([qc.invalidateQueries({ queryKey: settingsKeys.settings(profileId) }), qc.invalidateQueries({ queryKey: keys.profiles })])

  // Turning on needs the current PIN (the server re-checks it, throttled); returns an error key or null.
  const enrol = async (pin: string): Promise<Key | null> => {
    try {
      await enrolBiometric(pin)
      await refresh()
      setAsking(false)
      toast(t('settings.biometricEnabled'))
      return null
    } catch (e) {
      return errorKey(e, 'settings.biometricFailed')
    }
  }

  const turnOff = async () => {
    setBusy(true)
    try {
      await api.send('DELETE', '/webauthn/credentials')
      await refresh()
      toast(t('settings.biometricDisabled'))
    } catch (e) {
      toast(t(errorKey(e, 'settings.biometricFailed')), 'error')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="item">
      <span className="item__text">
        <span className="item__name">{t('settings.biometric')}</span>
        <span className="item__sub">{t(enabled ? 'settings.biometricIsOn' : 'settings.biometricIsOff')} · {t('settings.biometricHint')}</span>
        <span className="item__sub">{t('settings.biometricAnyFingerprint')}</span>
      </span>
      <Button variant={enabled ? 'ghost' : 'primary'} icon={FingerprintPattern} loading={busy}
        onClick={enabled ? turnOff : () => setAsking(true)}>
        {t(enabled ? 'settings.biometricTurnOff' : 'settings.biometricTurnOn')}
      </Button>
      <Sheet open={asking} onClose={() => setAsking(false)} title={t('settings.biometric')}>
        {asking && <EnrolBiometricForm onEnrol={enrol} />}
      </Sheet>
    </div>
  )
}

function LockSection({ profileId, info }: { profileId: number | null; info: SettingsInfo }) {
  const t = useT()
  const navigate = useNavigate()
  const { lock } = useLock()
  const [changing, setChanging] = useState(false)
  const owner = info.role === 'owner'
  return (
    <Section icon={KeyRound} title={t('settings.lock')}>
      {owner ? (
        <>
          <BiometricSetting profileId={profileId} enabled={info.has_biometric} />
          <Button variant="secondary" size="lg" block icon={KeyRound} onClick={() => setChanging(true)}>{t('settings.changePin')}</Button>
          <Sheet open={changing} onClose={() => setChanging(false)} title={t('settings.changePin')}>
            {changing && <ChangePinForm profileId={profileId} onDone={() => setChanging(false)} />}
          </Sheet>
        </>
      ) : <OwnerOnlyNote />}
      <Button variant="primary" size="lg" block icon={Lock} onClick={async () => { await lock().catch(() => {}); navigate('/lock', { replace: true }) }}>
        {t('lock.lockNow')}
      </Button>
    </Section>
  )
}

function AccessLogSection({ profileId, info }: { profileId: number | null; info: SettingsInfo }) {
  const t = useT()
  const [open, setOpen] = useState(false)
  return (
    <Section icon={ScrollText} title={t('settings.accessLog')} hint={t('settings.accessLogHint')}>
      {info.role === 'owner' ? (
        <>
          <Button variant="secondary" size="lg" block icon={ScrollText} onClick={() => setOpen(true)}>{t('settings.openAccessLog')}</Button>
          <Sheet open={open} onClose={() => setOpen(false)} title={t('settings.accessLog')}>
            {open && <AccessLog profileId={profileId} />}
          </Sheet>
        </>
      ) : <OwnerOnlyNote />}
    </Section>
  )
}

// --- page --------------------------------------------------------------------------------------------------

export function SettingsPage() {
  const t = useT()
  const navigate = useNavigate()
  const { profileId } = useLock()
  const info = useSettingsInfo(profileId)

  return (
    <div className="page">
      <DisplayTitle>{t('settings.title')}</DisplayTitle>
      {info.data && <p className="muted">{t('settings.signedInAs', { name: info.data.actor })}</p>}
      <LanguageSection profileId={profileId} />
      <TextSizeSection />
      <ThemeSection />
      <Button variant="secondary" size="lg" block icon={UserRound} onClick={() => navigate('/profile')}>{t('settings.openProfile')}</Button>
      {info.isPending && <div className="skeleton-stack" aria-busy="true"><Skeleton height={180} radius={20} /><Skeleton height={140} radius={20} /></div>}
      {info.isError && <ErrorState onRetry={() => { info.refetch() }} />}
      {info.data && (
        <>
          <EmergencyFieldsSection profileId={profileId} info={info.data} />
          <RepresentativesSection profileId={profileId} info={info.data} />
          <LockSection profileId={profileId} info={info.data} />
          <AccessLogSection profileId={profileId} info={info.data} />
        </>
      )}
      <Section icon={Info} title={t('settings.about')}>
        <div className="about">
          <p>{t('settings.aboutBody')}</p>
          <p>{t('settings.aboutListen')}</p>
        </div>
      </Section>
    </div>
  )
}
