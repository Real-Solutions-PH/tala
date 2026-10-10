// Placeholder pages: a title and an empty state each, until Waves 3–4 replace them with the real screens.
import type { ReactNode } from 'react'
import { Link, useParams } from 'react-router'
import {
  ArrowLeft, FileHeart, FileText, FlaskConical, Lock, MessageCircle, Pill, Settings, Siren, UserRound, WalletCards,
  type LucideIcon,
} from 'lucide-react'
import { useEmergency, useProfiles } from '../api/queries'
import { DisplayTitle } from '../components/DisplayTitle'
import { EmptyState } from '../components/EmptyState'
import { useLock } from '../features/lock/useLock'
import { useT, type Key } from '../i18n'

function Page({ title, icon, empty, children }: { title: string; icon: LucideIcon; empty?: { title: string; body: string }; children?: ReactNode }) {
  const t = useT()
  return (
    <div className="page">
      <DisplayTitle>{title}</DisplayTitle>
      {children}
      <EmptyState icon={icon} title={empty?.title ?? t('common.soonTitle')} body={empty?.body ?? t('common.soonBody')} />
    </div>
  )
}

// "Coming soon" rather than each page's real empty text, which would claim there is nothing on record.
const simple = (title: Key, icon: LucideIcon) => function SimplePage() {
  const t = useT()
  return <Page title={t(title)} icon={icon} />
}

export function ChatPage() {
  const t = useT()
  const { profileId } = useLock()
  const me = useProfiles().data?.find(p => p.id === profileId)
  const name = me ? (me.nickname ?? me.full_name) : ''
  return <Page title={t('nav.chat')} icon={MessageCircle} empty={{ title: t('chat.greeting', { name }), body: t('common.soonBody') }} />
}

export const CardsPage = simple('cards.title', WalletCards)
export const CardDetailPage = simple('cards.title', WalletCards)
export const MedsPage = simple('meds.title', Pill)
export const RecordsPage = simple('records.title', FileHeart)
export const LabPage = simple('records.labs', FlaskConical)
export const DocumentPage = simple('records.documents', FileText)
export const SettingsPage = simple('settings.title', Settings)
export const ProfilePage = simple('common.profile', UserRound)

/** Placeholder for Task 13's PIN screen. */
export function LockPage() {
  const t = useT()
  return (
    <main className="standalone">
      <Page title={t('lock.title')} icon={Lock} />
    </main>
  )
}

/** Public: a responder reads this without unlocking (spec section 3). Task 14 builds the full card. */
export function EmergencyPage() {
  const t = useT()
  const { pid } = useParams()
  const card = useEmergency(Number(pid) || null)
  return (
    <main className="standalone">
      <div className="page">
        <Link to="/chat" className="btn btn--ghost standalone__back">
          <ArrowLeft aria-hidden="true" strokeWidth={2} />
          <span>{t('common.back')}</span>
        </Link>
        <h1 className="emergency__title"><Siren aria-hidden="true" strokeWidth={2} /><span>{t('emergency.title')}</span></h1>
        {card.data && <p className="emergency__name">{card.data.name}</p>}
        <EmptyState icon={Siren} title={t('common.soonTitle')} body={t('common.soonBody')} />
      </div>
    </main>
  )
}
