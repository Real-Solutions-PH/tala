// Public emergency card (spec section 3): a responder reads it without unlocking. High contrast only:
// ink on surface, white on red. No muted text, so it stays readable at full brightness in the sun.
import { type ReactNode } from 'react'
import { Link, useParams } from 'react-router'
import { Phone, TriangleAlert, X } from 'lucide-react'
import { useEmergency } from '../../api/queries'
import type { EmergencyCard } from '../../api/types'
import { ErrorState } from '../../components/ErrorState'
import { Skeleton } from '../../components/Skeleton'
import { useT } from '../../i18n'
import { errorKey } from '../lock/errorKey'
import { useLock } from '../lock/useLock'
import './emergency.css'

/** "Ana Dela Cruz" → "Ana", for the "Tawagan si Ana" button. */
const firstName = (name: string) => name.trim().split(/\s+/)[0] ?? name

/** A labelled group, as in the prototype: a small caps label over tags or a panel. */
function Kv({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="kv" aria-label={title}>
      <h2>{title}</h2>
      {children}
    </section>
  )
}

/** One contact row: name and relation, the number as a tel: link named "Tawagan si …". */
function Contact({ name, sub, phone }: { name: string; sub: string | null; phone: string | null }) {
  const t = useT()
  return (
    <div className="contact">
      <span><b>{name}</b>{sub && <><br /><span className="sub">{sub}</span></>}</span>
      {phone && <a className="ph" href={`tel:${phone}`} aria-label={t('emergency.call', { name: firstName(name) })}><Phone aria-hidden="true" strokeWidth={2.25} />{phone}</a>}
    </div>
  )
}

function Body({ card }: { card: EmergencyCard }) {
  const t = useT()
  const none = <div className="tags"><span>{t('emergency.none')}</span></div>
  return (
    <>
      <Kv title={t('emergency.allergiesH')}>
        {card.allergies.length === 0 ? none : (
          <div className="tags al">
            {card.allergies.map(a => (
              <span key={a.substance} data-testid="allergy">
                <TriangleAlert aria-hidden="true" strokeWidth={2.5} /><span className="sr-only">{t('emergency.allergyBadge')}:</span>
                {a.substance}{a.reaction && <small> · {a.reaction}</small>}
              </span>
            ))}
          </div>
        )}
      </Kv>
      <Kv title={t('emergency.conditionsH')}>
        {card.conditions.length ? <div className="tags">{card.conditions.map(c => <span key={c}>{c}</span>)}</div> : none}
      </Kv>
      <Kv title={t('emergency.medicinesH')}>
        {card.meds.length ? <div className="tags">{card.meds.map(m => <span key={m.name}>{m.name}{m.strength && ` ${m.strength}`}</span>)}</div> : none}
      </Kv>
      {(card.contacts.length > 0 || card.doctor) && (
        <Kv title={t('emergency.contactsH')}>
          <div className="panel contacts">
            {card.contacts.map(c => <Contact key={c.phone + c.name} name={c.name} sub={c.relation} phone={c.phone} />)}
            {card.doctor && <Contact name={card.doctor.name} sub={card.doctor.clinic} phone={card.doctor.phone} />}
          </div>
        </Kv>
      )}
      <div className="qrwrap">
        <img className="ecard__qr" src={`/api/emergency/${card.profile_id}/qr.svg`} alt={t('emergency.qrAlt')} />
        <span>{t('emergency.qrNote')}</span>
      </div>
    </>
  )
}

/** The emergency card, a copy of the prototype's overlay: no unlock needed, blood type first. */
export function EmergencyPage() {
  const t = useT()
  const { pid } = useParams()
  const id = Number(pid) || null
  const card = useEmergency(id)
  const { profileId } = useLock() // a responder without a session goes back to the lock screen
  const data = card.data

  return (
    <main className="standalone ecard">
      <div className="ov-top">
        <Link to={profileId != null ? '/home' : '/lock'} className="iconbtn" title={t('common.back')}>
          <X aria-hidden="true" strokeWidth={2} /><span className="sr-only">{t('common.back')}</span>
        </Link>
        <h1>{t('emergency.title')}</h1>
        <span className="chip-s c-blue">{t('emergency.noUnlock')}</span>
      </div>
      <div className="ov-body">
        {card.isPending ? (
          <div className="ov-body" aria-busy="true">{[0, 1, 2].map(i => <Skeleton key={i} height={i ? 64 : 120} radius={16} />)}</div>
        ) : card.isError ? (
          <ErrorState message={errorKey(card.error)} onRetry={() => { card.refetch() }} />
        ) : data && (
          <>
            <div className="eheader ecard__band">
              <span className="mono">{t('emergency.bloodTypeCaps')}</span>
              <div className="bt"><b>{data.blood_type ?? '—'}</b><span>{data.name}{data.age != null && ` · ${t('emergency.yrs', { n: data.age })}`}</span></div>
            </div>
            <Body card={data} />
          </>
        )}
      </div>
    </main>
  )
}
