// Profile (Task 15): personal information (labels above 56px fields, inputmode per field), family history
// and contacts. Every change reports its outcome in a toast; every removal asks first.
import { useState, type FormEvent } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { HeartPulse, Phone, Plus, Save, Stethoscope, UserRound } from 'lucide-react'
import { api } from '../../api/client'
import { keys, useSummary } from '../../api/queries'
import type { Profile } from '../../api/types'
import { Badge } from '../../components/Badge'
import { Button } from '../../components/Button'
import { ErrorState } from '../../components/ErrorState'
import { Sheet } from '../../components/Sheet'
import { Skeleton } from '../../components/Skeleton'
import { useToast } from '../../components/Toast'
import { useT, type Key } from '../../i18n'
import { useLock } from '../lock/useLock'
import { settingsKeys, useFamilyHistory, useProfile } from './api'
import { ConfirmSheet } from './ConfirmSheet'
import { errorKey } from './errorKey'
import { Field, FormError, Section } from './parts'
import './settings.css'

type Form = Record<'full_name' | 'nickname' | 'birth_date' | 'sex' | 'blood_type' | 'phone' | 'address' | 'philhealth_no' | 'senior_id_no', string>
const BLOOD = ['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-']

const toForm = (p: Profile): Form => ({
  full_name: p.full_name ?? '', nickname: p.nickname ?? '', birth_date: p.birth_date ?? '', sex: p.sex ?? '',
  blood_type: p.blood_type ?? '', phone: p.phone ?? '', address: p.address ?? '',
  philhealth_no: p.philhealth_no ?? '', senior_id_no: p.senior_id_no ?? '',
})

function PersonalForm({ profileId, profile }: { profileId: number; profile: Profile }) {
  const t = useT()
  const toast = useToast()
  const qc = useQueryClient()
  const [form, setForm] = useState<Form>(() => toForm(profile))
  const [error, setError] = useState<Key | null>(null)
  const [busy, setBusy] = useState(false)

  const set = (k: keyof Form) => (e: { target: { value: string } }) => setForm(f => ({ ...f, [k]: e.target.value }))

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    if (!form.full_name.trim() || !form.birth_date) return setError('profile.required')
    setBusy(true)
    setError(null)
    const body = Object.fromEntries(Object.entries(form).map(([k, v]) => [k, v.trim() === '' && k !== 'full_name' ? null : v.trim()]))
    try {
      const saved = await api.send<Profile>('PUT', `/profiles/${profileId}`, body)
      qc.setQueryData(settingsKeys.profile(profileId), saved)
      qc.invalidateQueries({ queryKey: keys.summary(profileId) })
      qc.invalidateQueries({ queryKey: keys.profiles })
      toast(t('toasts.saved'))
    } catch (err) {
      setError(errorKey(err))
      toast(t('toasts.failed'), 'error')
    } finally {
      setBusy(false)
    }
  }

  const text = (k: keyof Form, inputMode: 'text' | 'tel' | 'numeric', autoComplete = 'off') =>
    ({ id }: { id: string }) => (
      <input id={id} className="field__input" value={form[k]} onChange={set(k)} inputMode={inputMode}
        type={inputMode === 'tel' ? 'tel' : 'text'} autoComplete={autoComplete} />
    )

  return (
    <form className="form" onSubmit={submit} noValidate>
      <Field label={t('fields.full_name')}>{text('full_name', 'text', 'name')}</Field>
      <Field label={t('fields.nickname')}>{text('nickname', 'text', 'nickname')}</Field>
      <div className="field-row">
        <Field label={t('fields.birth_date')}>
          {({ id }) => <input id={id} className="field__input" type="date" value={form.birth_date} onChange={set('birth_date')} autoComplete="bday" />}
        </Field>
        <Field label={t('fields.sex')}>
          {({ id }) => (
            <select id={id} className="field__input" value={form.sex} onChange={set('sex')}>
              <option value="">—</option>
              <option value="F">{t('profile.sexF')}</option>
              <option value="M">{t('profile.sexM')}</option>
            </select>
          )}
        </Field>
      </div>
      <Field label={t('fields.blood_type')}>
        {({ id }) => (
          <select id={id} className="field__input" value={form.blood_type} onChange={set('blood_type')}>
            <option value="">{t('profile.bloodUnknown')}</option>
            {BLOOD.map(b => <option key={b} value={b}>{b}</option>)}
          </select>
        )}
      </Field>
      <Field label={t('fields.phone')}>{text('phone', 'tel', 'tel')}</Field>
      <Field label={t('fields.address')}>{text('address', 'text', 'street-address')}</Field>
      <Field label={t('fields.philhealth_no')}>{text('philhealth_no', 'numeric')}</Field>
      <Field label={t('fields.senior_id_no')}>{text('senior_id_no', 'text')}</Field>
      <FormError message={error && t(error)} />
      <Button type="submit" size="lg" block icon={Save} loading={busy}>{t('profile.save')}</Button>
    </form>
  )
}

type Removing = { kind: 'family' | 'contact'; id: number; name: string }

function AddFamilyForm({ profileId, onDone }: { profileId: number; onDone: () => void }) {
  const t = useT()
  const toast = useToast()
  const qc = useQueryClient()
  const [relation, setRelation] = useState('')
  const [condition, setCondition] = useState('')
  const [error, setError] = useState<Key | null>(null)
  const [busy, setBusy] = useState(false)
  const submit = async (e: FormEvent) => {
    e.preventDefault()
    if (!relation.trim() || !condition.trim()) return setError('profile.required')
    setBusy(true)
    try {
      await api.send('POST', `/profiles/${profileId}/family-history`, { relation: relation.trim(), condition: condition.trim() })
      await qc.invalidateQueries({ queryKey: settingsKeys.family(profileId) })
      toast(t('toasts.saved'))
      onDone()
    } catch (err) {
      setError(errorKey(err))
    } finally {
      setBusy(false)
    }
  }
  return (
    <form className="form" onSubmit={submit} noValidate>
      <Field label={t('profile.familyRelation')}>
        {({ id }) => <input id={id} className="field__input" value={relation} onChange={e => setRelation(e.target.value)} inputMode="text" autoComplete="off" maxLength={40} />}
      </Field>
      <Field label={t('profile.familyCondition')}>
        {({ id }) => <input id={id} className="field__input" value={condition} onChange={e => setCondition(e.target.value)} inputMode="text" autoComplete="off" maxLength={120} />}
      </Field>
      <FormError message={error && t(error)} />
      <Button type="submit" size="lg" block icon={Plus} loading={busy}>{t('common.save')}</Button>
    </form>
  )
}

function AddContactForm({ profileId, onDone }: { profileId: number; onDone: () => void }) {
  const t = useT()
  const toast = useToast()
  const qc = useQueryClient()
  const [name, setName] = useState('')
  const [relation, setRelation] = useState('')
  const [phone, setPhone] = useState('')
  const [error, setError] = useState<Key | null>(null)
  const [busy, setBusy] = useState(false)
  const submit = async (e: FormEvent) => {
    e.preventDefault()
    if (!name.trim() || phone.trim().length < 3) return setError('profile.required')
    setBusy(true)
    try {
      await api.send('POST', `/profiles/${profileId}/contacts`, { name: name.trim(), relation: relation.trim() || null, phone: phone.trim() })
      await qc.invalidateQueries({ queryKey: keys.summary(profileId) })
      qc.invalidateQueries({ queryKey: keys.emergency(profileId) })
      toast(t('toasts.saved'))
      onDone()
    } catch (err) {
      setError(errorKey(err))
    } finally {
      setBusy(false)
    }
  }
  return (
    <form className="form" onSubmit={submit} noValidate>
      <Field label={t('profile.contactName')}>
        {({ id }) => <input id={id} className="field__input" value={name} onChange={e => setName(e.target.value)} inputMode="text" autoComplete="off" maxLength={80} />}
      </Field>
      <Field label={t('profile.contactRelation')}>
        {({ id }) => <input id={id} className="field__input" value={relation} onChange={e => setRelation(e.target.value)} inputMode="text" autoComplete="off" maxLength={40} />}
      </Field>
      <Field label={t('profile.contactPhone')}>
        {({ id }) => <input id={id} className="field__input tabular" type="tel" value={phone} onChange={e => setPhone(e.target.value)} inputMode="tel" autoComplete="off" maxLength={30} />}
      </Field>
      <FormError message={error && t(error)} />
      <Button type="submit" size="lg" block icon={Plus} loading={busy}>{t('common.save')}</Button>
    </form>
  )
}

export function ProfilePage() {
  const t = useT()
  const toast = useToast()
  const qc = useQueryClient()
  const { profileId } = useLock()
  const profile = useProfile(profileId)
  const family = useFamilyHistory(profileId)
  const summary = useSummary(profileId)
  const [adding, setAdding] = useState<'family' | 'contact' | null>(null)
  const [removing, setRemoving] = useState<Removing | null>(null)
  const [busy, setBusy] = useState(false)
  if (profileId == null) return null

  const remove = async () => {
    if (!removing) return
    setBusy(true)
    try {
      const path = removing.kind === 'family' ? 'family-history' : 'contacts'
      await api.send('DELETE', `/profiles/${profileId}/${path}/${removing.id}`)
      await qc.invalidateQueries({ queryKey: removing.kind === 'family' ? settingsKeys.family(profileId) : keys.summary(profileId) })
      toast(t('toasts.deleted'))
      setRemoving(null)
    } catch (e) {
      toast(t(errorKey(e)), 'error')
    } finally {
      setBusy(false)
    }
  }

  const contacts = summary.data?.contacts ?? []

  return (
    <div className="page">
      <h1>{t('profile.title')}</h1>

      <Section icon={UserRound} title={t('profile.personal')}>
        {profile.isPending && <div className="skeleton-stack" aria-busy="true">{[0, 1, 2, 3].map(i => <Skeleton key={i} height={84} />)}</div>}
        {profile.isError && <ErrorState onRetry={() => { profile.refetch() }} />}
        {profile.data && <PersonalForm profileId={profileId} profile={profile.data} />}
      </Section>

      <Section icon={HeartPulse} title={t('profile.familyHistory')} hint={t('profile.familyHint')}>
        {family.isPending && <Skeleton height={64} />}
        {family.isError && <ErrorState onRetry={() => { family.refetch() }} />}
        {family.data && (family.data.length === 0 ? <p className="muted">{t('profile.noFamily')}</p> : (
          <ul className="item-list">
            {family.data.map(f => (
              <li key={f.id} className="item">
                <span className="item__text">
                  <span className="item__name">{f.condition}</span>
                  <span className="item__sub">{f.relation}</span>
                </span>
                <Button variant="ghost" aria-label={`${t('settings.remove')}: ${f.condition}`}
                  onClick={() => setRemoving({ kind: 'family', id: f.id, name: `${f.condition} (${f.relation})` })}>{t('settings.remove')}</Button>
              </li>
            ))}
          </ul>
        ))}
        <Button variant="secondary" size="lg" block icon={Plus} onClick={() => setAdding('family')}>{t('profile.addFamily')}</Button>
      </Section>

      <Section icon={Phone} title={t('profile.contacts')} hint={t('profile.contactsHint')}>
        {summary.isPending && <Skeleton height={64} />}
        {summary.data && (contacts.length === 0 ? <p className="muted">{t('profile.noContacts')}</p> : (
          <ul className="item-list">
            {contacts.map(c => (
              <li key={c.id} className="item">
                <span className="item__text">
                  <span className="item__name">{c.name}</span>
                  <span className="item__sub">{[c.relation, c.phone].filter(Boolean).join(' · ')}</span>
                  {(c.is_doctor === 1 || c.is_emergency === 1) && (
                    <span className="chip-row">
                      {c.is_doctor === 1 && <Badge tone="info" icon={Stethoscope}>{t('profile.doctorTag')}</Badge>}
                      {c.is_emergency === 1 && <Badge tone="danger" icon={Phone}>{t('profile.emergencyTag')}</Badge>}
                    </span>
                  )}
                </span>
                <Button variant="ghost" aria-label={`${t('settings.remove')}: ${c.name}`}
                  onClick={() => setRemoving({ kind: 'contact', id: c.id, name: c.name })}>{t('settings.remove')}</Button>
              </li>
            ))}
          </ul>
        ))}
        <Button variant="secondary" size="lg" block icon={Plus} onClick={() => setAdding('contact')}>{t('profile.addContact')}</Button>
      </Section>

      <Sheet open={adding === 'family'} onClose={() => setAdding(null)} title={t('profile.addFamily')}>
        {adding === 'family' && <AddFamilyForm profileId={profileId} onDone={() => setAdding(null)} />}
      </Sheet>
      <Sheet open={adding === 'contact'} onClose={() => setAdding(null)} title={t('profile.addContact')}>
        {adding === 'contact' && <AddContactForm profileId={profileId} onDone={() => setAdding(null)} />}
      </Sheet>
      <ConfirmSheet open={removing != null} onClose={() => setRemoving(null)} busy={busy} onConfirm={remove}
        title={t('profile.removeTitle', { name: removing?.name ?? '' })} body={t('profile.removeBody')}
        confirmLabel={t('profile.removeConfirm')} />
    </div>
  )
}
