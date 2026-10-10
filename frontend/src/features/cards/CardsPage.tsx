// ID wallet: cards as large 16:10 thumbnails, an expiry badge when a card runs out within 60 days,
// a full-screen viewer at /cards/:id, and an Add card sheet (POST multipart front and back).
import { useCallback, useEffect, useRef, useState, type FormEvent } from 'react'
import { Link, useLocation, useNavigate, useParams } from 'react-router'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { CalendarClock, Camera, Plus, WalletCards } from 'lucide-react'
import type React from 'react'
import { api } from '../../api/client'
import { keys, useCards, useSummary } from '../../api/queries'
import type { WalletCard } from '../../api/types'
import { Badge } from '../../components/Badge'
import { Button } from '../../components/Button'
import { DisplayTitle } from '../../components/DisplayTitle'
import { EmptyState } from '../../components/EmptyState'
import { ErrorState } from '../../components/ErrorState'
import { Sheet } from '../../components/Sheet'
import { Skeleton } from '../../components/Skeleton'
import { useToast } from '../../components/Toast'
import { formatDate, useLang, useT, type Key } from '../../i18n'
import { errorKey } from '../lock/errorKey'
import { useLock } from '../lock/useLock'
import { CardViewer } from './CardViewer'
import './cards.css'

const DAY = 86_400_000
const KINDS: WalletCard['kind'][] = ['philhealth', 'senior', 'hmo', 'pwd', 'vaccination', 'national_id', 'other']

function ExpiryBadge({ expires, now }: { expires: string | null; now: number }) {
  const t = useT()
  const [lang] = useLang()
  if (!expires) return null
  const days = (new Date(`${expires}T23:59:59`).getTime() - now) / DAY
  if (days > 60) return null
  const date = formatDate(expires, lang)
  return days < 0
    ? <Badge tone="danger" icon={CalendarClock}>{t('cards.expired', { date })}</Badge>
    : <Badge tone="warn" icon={CalendarClock}>{t('cards.expiresSoon', { date })}</Badge>
}

/** Card thumbnail. A failed image is retried once, then shows a labelled placeholder instead of a broken icon. */
const CARD_BG: Record<WalletCard['kind'], string> = {
  philhealth: 'var(--card-a)', hmo: 'var(--card-b)', senior: 'var(--card-c)', pwd: 'var(--card-c)', national_id: 'var(--card-c)',
  vaccination: 'var(--card-d)', other: 'var(--card-d)',
}

/** The prototype's wallet card: a gradient card with the name, its kind, the number, the holder and the birth date. */
function WCard({ c, holder, dob }: { c: WalletCard; holder: string; dob: string | null }) {
  const t = useT()
  return (
    <span className="wcard" style={{ '--wc': CARD_BG[c.kind] } as React.CSSProperties}>
      <span className="wcard__t"><b>{c.label}</b><span>{t(`cards.${c.kind}` as Key)}</span></span>
      <span className="wcard__num tabular">{c.number_masked ?? ''}</span>
      <span className="wcard__nm"><span>{holder.toUpperCase()}</span>{dob && <span>{t('cards.dob', { date: dob })}</span>}</span>
    </span>
  )
}

function AddCardSheet({ open, onClose }: { open: boolean; onClose: () => void }) {
  const t = useT()
  const toast = useToast()
  const qc = useQueryClient()
  const { profileId } = useLock()
  const [kind, setKind] = useState<WalletCard['kind']>('philhealth')
  const [label, setLabel] = useState(t('cards.philhealth'))
  const [labelTouched, setLabelTouched] = useState(false)
  const [number, setNumber] = useState('')
  const [front, setFront] = useState<File | null>(null)
  const [back, setBack] = useState<File | null>(null)
  const [error, setError] = useState<Key | null>(null)

  const add = useMutation({
    mutationFn: () => {
      const fd = new FormData()
      fd.append('kind', kind)
      fd.append('label', label.trim() || t(`cards.${kind}`))
      if (number.trim()) fd.append('number', number.trim())
      fd.append('front', front!)
      if (back) fd.append('back', back)
      return api.send<WalletCard>('POST', `/profiles/${profileId}/cards`, fd)
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: keys.cards(profileId) })
      toast(t('toasts.cardAdded'))
      setFront(null); setBack(null); setNumber(''); setError(null)
      onClose()
    },
    onError: err => {
      const k = errorKey(err, 'toasts.failed')
      setError(k)
      toast(t(k), 'error')
    },
  })

  const submit = (e: FormEvent) => {
    e.preventDefault()
    if (!front) { setError('cards.frontRequired'); return }
    setError(null)
    add.mutate()
  }

  const chooseKind = (k: WalletCard['kind']) => {
    setKind(k)
    if (!labelTouched) setLabel(t(`cards.${k}`))
  }

  return (
    <Sheet open={open} onClose={onClose} title={t('cards.addCard')}>
      {open && (
        <form className="addcard" onSubmit={submit} noValidate>
          <label className="field">
            <span className="field__label">{t('cards.kind')}</span>
            <select className="field__input" value={kind} onChange={e => chooseKind(e.target.value as WalletCard['kind'])}>
              {KINDS.map(k => <option key={k} value={k}>{t(`cards.${k}`)}</option>)}
            </select>
          </label>
          <label className="field">
            <span className="field__label">{t('cards.label')}</span>
            <input className="field__input" value={label} onChange={e => { setLabel(e.target.value); setLabelTouched(true) }} />
          </label>
          <label className="field">
            <span className="field__label">{t('cards.number')}</span>
            <input className="field__input" value={number} onChange={e => setNumber(e.target.value)} inputMode="text" autoComplete="off" />
          </label>
          <label className="field field--file">
            <span className="field__label">{t('cards.frontPhoto')}</span>
            <span className="field__file"><Camera aria-hidden="true" strokeWidth={2} /><span>{front?.name ?? t('common.takePhoto')}</span></span>
            <input className="sr-only" type="file" accept="image/*" capture="environment"
              onChange={e => { setFront(e.target.files?.[0] ?? null); setError(null) }} />
          </label>
          <label className="field field--file">
            <span className="field__label">{t('cards.backPhoto')}</span>
            <span className="field__file"><Camera aria-hidden="true" strokeWidth={2} /><span>{back?.name ?? t('common.takePhoto')}</span></span>
            <input className="sr-only" type="file" accept="image/*" capture="environment"
              onChange={e => setBack(e.target.files?.[0] ?? null)} />
          </label>
          {error && <p className="addcard__error" role="alert">{t(error)}</p>}
          <Button type="submit" size="lg" block loading={add.isPending}>{t('cards.saveCard')}</Button>
        </form>
      )}
    </Sheet>
  )
}

export function CardsPage() {
  const t = useT()
  const { profileId } = useLock()
  const cards = useCards(profileId)
  const profile = useSummary(profileId).data?.profile
  const [lang] = useLang()
  const [adding, setAdding] = useState(false)
  const [now] = useState(() => Date.now())
  const location = useLocation()
  const listRef = useRef<HTMLUListElement>(null)
  // Back from the viewer: return focus to the thumbnail that opened it.
  const returnTo = (location.state as { focusCard?: number } | null)?.focusCard
  const hasCards = (cards.data?.length ?? 0) > 0
  useEffect(() => {
    if (returnTo == null || !hasCards) return
    listRef.current?.querySelector<HTMLElement>(`[data-card-id="${returnTo}"]`)?.focus()
  }, [returnTo, hasCards])

  return (
    <div className="page">
      <div className="greet">
        <h1 className="h">{t('cards.myCards')}</h1>
        <p className="sub">{t('cards.tapHint')}</p>
      </div>
      {cards.isPending ? (
        <ul className="wallet" aria-busy="true">
          {[0, 1].map(i => (
            <li key={i} className="wallet__item">
              <Skeleton className="wallet__thumb" height="auto" radius={20} />
              <Skeleton width="50%" height={24} />
            </li>
          ))}
        </ul>
      ) : cards.isError ? (
        <ErrorState message={errorKey(cards.error)} onRetry={() => { cards.refetch() }} />
      ) : cards.data.length === 0 ? (
        <EmptyState icon={WalletCards} title={t('cards.emptyNoCards')} body={t('cards.emptyPhoto')}
          action={{ label: t('cards.addCard'), icon: Camera, onClick: () => setAdding(true) }} />
      ) : (
        <>
          <ul className="wallet" ref={listRef}>
            {cards.data.map(c => (
              <li key={c.id} className="wallet__item">
                <Link to={`/cards/${c.id}`} className="wallet__link" data-card-id={c.id} aria-label={c.label}>
                  <WCard c={c} holder={profile?.full_name ?? ''} dob={profile?.birth_date ? formatDate(profile.birth_date, lang, { month: '2-digit', day: '2-digit', year: 'numeric' }) : null} />
                </Link>
                <ExpiryBadge expires={c.expires} now={now} />
              </li>
            ))}
          </ul>
          <button type="button" className="scanbtn" onClick={() => setAdding(true)}><Plus aria-hidden="true" strokeWidth={2} /><span><b>{t('cards.addCard')}</b></span></button>
        </>
      )}
      <AddCardSheet open={adding} onClose={() => setAdding(false)} />
    </div>
  )
}

/** /cards/:id — the full-screen viewer for one card. */
export function CardDetailPage() {
  const t = useT()
  const navigate = useNavigate()
  const { id } = useParams()
  const { profileId } = useLock()
  const cards = useCards(profileId)
  const card = cards.data?.find(c => c.id === Number(id))
  const from = (useLocation().state as { from?: string } | null)?.from
  // Opened from a chat: go back to that conversation. Otherwise back to the wallet.
  const close = useCallback(() => (from ? navigate(-1) : navigate('/cards', { state: { focusCard: Number(id) } })), [navigate, id, from])

  if (card) return <CardViewer card={card} onClose={close} />
  return (
    <div className="page">
      <DisplayTitle>{t('cards.title')}</DisplayTitle>
      {cards.isPending ? <Skeleton className="wallet__thumb" height="auto" radius={20} />
        : cards.isError ? <ErrorState message={errorKey(cards.error)} onRetry={() => { cards.refetch() }} />
        : <EmptyState icon={WalletCards} title={t('errors.notFound')} body={t('cards.emptyPhoto')}
            action={{ label: t('common.back'), onClick: close }} />}
    </div>
  )
}
