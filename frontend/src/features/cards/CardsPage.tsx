// ID wallet: cards as large 16:10 thumbnails, an expiry badge when a card runs out within 60 days,
// a full-screen viewer at /cards/:id, and an Add card sheet (POST multipart front and back).
import { useCallback, useEffect, useRef, useState, type FormEvent } from 'react'
import { Link, useLocation, useNavigate, useParams } from 'react-router'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { CalendarClock, Camera, Plus, WalletCards } from 'lucide-react'
import { api } from '../../api/client'
import { keys, useCards } from '../../api/queries'
import type { WalletCard } from '../../api/types'
import { Badge } from '../../components/Badge'
import { Button } from '../../components/Button'
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
function Thumb({ src }: { src: string }) {
  const [tries, setTries] = useState(0)
  if (tries > 1) {
    return <span className="wallet__thumb wallet__thumb--none" aria-hidden="true"><WalletCards strokeWidth={1.5} /></span>
  }
  return (
    <img className="wallet__thumb" src={tries ? `${src}?retry=1` : src} alt="" loading="lazy"
      onError={() => { setTimeout(() => setTries(n => n + 1), tries ? 0 : 400) }} />
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
      <h1>{t('cards.title')}</h1>
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
                <Link to={`/cards/${c.id}`} className="wallet__link" data-card-id={c.id}>
                  <Thumb src={c.front_url} />
                  <span className="wallet__label">{c.label}</span>
                </Link>
                <ExpiryBadge expires={c.expires} now={now} />
              </li>
            ))}
          </ul>
          <Button size="lg" variant="secondary" block icon={Plus} onClick={() => setAdding(true)}>{t('cards.addCard')}</Button>
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
  const close = useCallback(() => navigate('/cards', { state: { focusCard: Number(id) } }), [navigate, id])

  if (card) return <CardViewer card={card} onClose={close} />
  return (
    <div className="page">
      <h1>{t('cards.title')}</h1>
      {cards.isPending ? <Skeleton className="wallet__thumb" height="auto" radius={20} />
        : cards.isError ? <ErrorState message={errorKey(cards.error)} onRetry={() => { cards.refetch() }} />
        : <EmptyState icon={WalletCards} title={t('errors.notFound')} body={t('cards.emptyPhoto')}
            action={{ label: t('common.back'), onClick: close }} />}
    </div>
  )
}
