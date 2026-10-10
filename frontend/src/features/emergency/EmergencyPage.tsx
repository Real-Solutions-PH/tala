// Public emergency card (spec section 3): a responder reads it without unlocking. High contrast only:
// ink on surface, white on red. No muted text, so it stays readable at full brightness in the sun.
import { useState, type ReactNode } from 'react'
import { Link, useParams } from 'react-router'
import { ArrowLeft, Droplet, HeartPulse, Phone, Pill, QrCode, Siren, Stethoscope, TriangleAlert, UserRound, Users, IdCard } from 'lucide-react'
import { useEmergency } from '../../api/queries'
import type { EmergencyCard } from '../../api/types'
import { ErrorState } from '../../components/ErrorState'
import { Sheet } from '../../components/Sheet'
import { Skeleton } from '../../components/Skeleton'
import { useT } from '../../i18n'
import { errorKey } from '../lock/errorKey'
import { useLock } from '../lock/useLock'
import './emergency.css'

/** "Ana Dela Cruz" → "Ana", for the "Tawagan si Ana" button. */
const firstName = (name: string) => name.trim().split(/\s+/)[0] ?? name

function Row({ icon: Icon, title, alert, children }: { icon: typeof Siren; title: string; alert?: boolean; children: ReactNode }) {
  return (
    <section className={alert ? 'ecard__row ecard__row--alert' : 'ecard__row'} aria-label={title}>
      <h2 className="ecard__label"><span className="ecard__icon"><Icon aria-hidden="true" strokeWidth={1.75} /></span><span>{title}</span></h2>
      <div className="ecard__value">{children}</div>
    </section>
  )
}

function CallButton({ name, phone }: { name: string; phone: string }) {
  const t = useT()
  return (
    <a className="ecard__call" href={`tel:${phone}`}>
      <Phone aria-hidden="true" strokeWidth={2.25} />
      <span>{t('emergency.call', { name })}</span>
    </a>
  )
}

function Body({ card }: { card: EmergencyCard }) {
  const t = useT()
  const none = <p>{t('emergency.noneListed')}</p>
  return (
    <div className="ecard__rows">
      <Row icon={TriangleAlert} title={t('emergency.allergies')} alert={card.allergies.length > 0}>
        {card.allergies.length === 0 ? <p>{t('emergency.noAllergies')}</p> : (
          <ul className="ecard__list">
            {card.allergies.map(a => (
              <li key={a.substance} className="ecard__allergy">
                <span className="ecard__allergy-badge" data-testid="allergy">
                  <TriangleAlert aria-hidden="true" strokeWidth={2.5} />
                  <span>{t('emergency.allergyBadge')}:</span>
                  <strong>{a.substance}</strong>
                </span>
                {a.reaction && <span className="ecard__reaction">{a.reaction}</span>}
              </li>
            ))}
          </ul>
        )}
      </Row>
      <Row icon={HeartPulse} title={t('emergency.conditions')}>
        {card.conditions.length ? <ul className="ecard__list ecard__bullets">{card.conditions.map(c => <li key={c}>{c}</li>)}</ul> : none}
      </Row>
      <Row icon={Pill} title={t('emergency.meds')}>
        {card.meds.length ? (
          <ul className="ecard__list ecard__bullets">
            {card.meds.map(m => (
              <li key={m.name}><span><strong>{m.name}</strong>{m.strength && ` ${m.strength}`}</span>
                {m.schedule.length > 0 && <span className="ecard__sched">{m.schedule.map(h => <span key={h} className="ecard__time">{h}</span>)}</span>}</li>
            ))}
          </ul>
        ) : none}
      </Row>
      <Row icon={Users} title={t('emergency.contacts')}>
        {card.contacts.length ? (
          <ul className="ecard__list">
            {card.contacts.map(c => (
              <li key={c.phone + c.name} className="ecard__contact">
                <p><strong>{c.name}</strong>{c.relation && ` · ${c.relation}`}</p>
                <p className="tabular">{c.phone}</p>
                <CallButton name={firstName(c.name)} phone={c.phone} />
              </li>
            ))}
          </ul>
        ) : none}
      </Row>
      {card.doctor && (
        <Row icon={Stethoscope} title={t('emergency.doctor')}>
          <div className="ecard__contact">
            <p><strong>{card.doctor.name}</strong></p>
            {card.doctor.clinic && <p>{card.doctor.clinic}</p>}
            {card.doctor.phone && <p className="tabular">{card.doctor.phone}</p>}
            {card.doctor.phone && <CallButton name={card.doctor.name} phone={card.doctor.phone} />}
          </div>
        </Row>
      )}
    </div>
  )
}

export function EmergencyPage() {
  const t = useT()
  const { pid } = useParams()
  const id = Number(pid) || null
  const card = useEmergency(id)
  const [qrOpen, setQrOpen] = useState(false)
  const { profileId } = useLock() // a responder without a session goes back to the lock screen
  const data = card.data

  return (
    <main className="standalone ecard">
      <header className="ecard__band">
        <div className="ecard__bar">
          <Link to={profileId != null ? '/chat' : '/lock'} className="ecard__back" title={t('common.back')}>
            <ArrowLeft aria-hidden="true" />
            <span className="sr-only">{t('common.back')}</span>
          </Link>
          {data && (
            <button type="button" className="ecard__qrbtn" onClick={() => setQrOpen(true)}>
              <QrCode aria-hidden="true" strokeWidth={1.75} /><span>{t('emergency.showQr')}</span>
            </button>
          )}
        </div>
        <h1 className="ecard__title"><Siren aria-hidden="true" strokeWidth={1.75} /><span>{t('emergency.title')}</span></h1>
        {card.isPending ? (
          <div className="ecard__who"><Skeleton width={72} height={72} radius={14} /><Skeleton width="60%" height={32} /></div>
        ) : data && (
          <>
            <div className="ecard__who">
              {data.photo_url
                ? <img className="ecard__photo" src={data.photo_url} alt="" width={72} height={72} />
                : <span className="ecard__photo ecard__photo--none" aria-hidden="true"><UserRound strokeWidth={1.75} /></span>}
              <div>
                <p className="ecard__name">{data.name}</p>
                {data.age != null && <p className="ecard__age">{t('emergency.years', { n: data.age })}</p>}
              </div>
            </div>
            {(data.blood_type || data.philhealth_last4) && (
              // The two facts a nurse asks first, as white tiles on the band (the reference's results tiles).
              <dl className="ecard__facts">
                {data.blood_type && (
                  <div className="ecard__fact"><dt><Droplet aria-hidden="true" strokeWidth={1.75} />{t('emergency.bloodType')}</dt><dd className="ecard__big">{data.blood_type}</dd></div>
                )}
                {data.philhealth_last4 && (
                  <div className="ecard__fact"><dt><IdCard aria-hidden="true" strokeWidth={1.75} />{t('emergency.philhealth')}</dt><dd className="ecard__big tabular">•••• {data.philhealth_last4}</dd></div>
                )}
              </dl>
            )}
          </>
        )}
      </header>

      <div className="ecard__content">
        {card.isPending ? (
          <div className="ecard__rows" aria-busy="true">
            {[0, 1, 2, 3].map(i => <Skeleton key={i} height={96} radius={20} />)}
          </div>
        ) : card.isError ? (
          <ErrorState message={errorKey(card.error)} onRetry={() => { card.refetch() }} />
        ) : data && (
          <>
            <Body card={data} />
            <Sheet open={qrOpen} onClose={() => setQrOpen(false)} title={t('emergency.showQr')}>
              {qrOpen && (
                <div className="ecard__qrbox">
                  <img className="ecard__qr" src={`/api/emergency/${data.profile_id}/qr.svg`} alt={t('emergency.qrAlt')} />
                  <p className="ecard__qrhint">{t('emergency.qr')}</p>
                </div>
              )}
            </Sheet>
          </>
        )}
      </div>
    </main>
  )
}
