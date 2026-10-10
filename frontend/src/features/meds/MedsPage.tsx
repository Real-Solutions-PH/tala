// Medicines: today's doses grouped Umaga / Tanghali / Gabi with an optimistic "Markahang nainom" action
// that turns into the "Nainom na" status (tap again to undo),
// refill warnings, and the full list with purpose and prescriber.
import { useMemo, useState } from 'react'
import { localDate, periodOf, REFILL_AT, scheduleOf, slotTime, useToggleDose, type Dose, type Period } from './doses'
import { Check, PackageOpen, Pill, Stethoscope, Sun, Sunrise, Moon, type LucideIcon } from 'lucide-react'
import { useMeds } from '../../api/queries'
import type { Med } from '../../api/types'
import { Badge } from '../../components/Badge'
import { DisplayTitle } from '../../components/DisplayTitle'
import { EmptyState } from '../../components/EmptyState'
import { ErrorState } from '../../components/ErrorState'
import { Skeleton } from '../../components/Skeleton'
import { formatDate, useLang, useT, type Key } from '../../i18n'
import { errorKey } from '../lock/errorKey'
import { useLock } from '../lock/useLock'
import './meds.css'

const PERIODS: { id: Period; label: Key; icon: LucideIcon }[] = [
  { id: 'morning', label: 'meds.morning', icon: Sunrise },
  { id: 'noon', label: 'meds.noon', icon: Sun },
  { id: 'night', label: 'meds.night', icon: Moon },
]
function RefillBadge({ med }: { med: Med | undefined }) {
  const t = useT()
  if (med?.supply_left == null || med.supply_left > REFILL_AT) return null
  return <Badge tone="warn" icon={PackageOpen}>{t('meds.refillSoon', { n: med.supply_left })}</Badge>
}

/** One dose, after the prototype: the whole row is the button. A round tick, the name and time, a status chip. */
function DoseRow({ dose, med, onToggle }: { dose: Dose; med: Med | undefined; onToggle: (d: Dose) => void }) {
  const t = useT()
  const [lang] = useLang()
  const taken = dose.taken_at != null
  const name = dose.name ?? med?.name ?? ''
  const strength = dose.strength ?? med?.strength
  return (
    <li className={['dose', taken && 'dose--taken'].filter(Boolean).join(' ')} data-testid="dose">
      <button type="button" className="dose__row" aria-pressed={taken} onClick={() => onToggle(dose)}>
        <span className="sr-only">{t(taken ? 'meds.taken' : 'meds.markTaken')}</span>
        <span className="dose__tick" aria-hidden="true">{taken && <Check strokeWidth={3} />}</span>
        <span className="dose__info">
          <span className="dose__name">{name}{strength && <span className="dose__strength"> {strength}</span>}</span>
          <span className="dose__meta tabular">
            {taken && dose.taken_at
              ? t('meds.takenAt', { time: formatDate(dose.taken_at, lang, { hour: 'numeric', minute: '2-digit' }) })
              : slotTime(dose.slot, lang)}
          </span>
        </span>
        <span className="dose__chip" aria-hidden="true">{t(taken ? 'meds.taken' : 'meds.due')}</span>
      </button>
    </li>
  )
}

function MedsSkeleton() {
  return (
    <div className="meds__skeleton" aria-busy="true">
      <Skeleton width="40%" height={28} />
      {[0, 1, 2].map(i => <Skeleton key={i} height={88} radius={20} />)}
    </div>
  )
}

export function MedsPage() {
  const t = useT()
  const [lang] = useLang()
  const { profileId } = useLock()
  const [now] = useState(() => new Date())
  const date = useMemo(() => localDate(now), [now])
  const meds = useMeds(profileId, date)

  const onToggle = useToggleDose(profileId, date, meds.data)
  const byId = useMemo(() => new Map((meds.data?.meds ?? []).map(m => [m.id, m])), [meds.data])
  const groups = useMemo(() => {
    const g: Record<Period, Dose[]> = { morning: [], noon: [], night: [] }
    for (const d of (meds.data?.today ?? []) as Dose[]) g[periodOf(d.slot)].push(d)
    return g
  }, [meds.data])


  return (
    <div className="page meds">
      <DisplayTitle>{t('meds.title')}</DisplayTitle>
      {meds.isPending ? <MedsSkeleton />
        : meds.isError ? <ErrorState message={errorKey(meds.error)} onRetry={() => { meds.refetch() }} />
        : meds.data.meds.length === 0 ? <EmptyState icon={Pill} title={t('meds.emptyTitle')} body={t('meds.emptyBody')} />
        : (
          <>
            <p className="muted meds__hint">{formatDate(now, lang, { weekday: 'long', month: 'long', day: 'numeric' })} · {t('meds.tapHint')}</p>
            {meds.data.meds.filter(m => m.supply_left != null && m.supply_left <= REFILL_AT).map(m => (
              <p key={m.id} className="refill" role="note"><PackageOpen aria-hidden="true" strokeWidth={2} />
                <span>{t('meds.refillBanner', { name: [m.name, m.strength].filter(Boolean).join(' '), n: m.supply_left ?? 0 })}</span></p>
            ))}
            <section className="meds__section" aria-labelledby="meds-today">
              <h2 id="meds-today" className="meds__h2">{t('meds.todayHeading')}</h2>
              {PERIODS.filter(p => groups[p.id].length > 0).map(({ id, label, icon: Icon }) => (
                <section key={id} className="meds__period" aria-labelledby={`period-${id}`}>
                  <h3 id={`period-${id}`} className="meds__h3"><Icon aria-hidden="true" strokeWidth={2} /><span>{t(label)}</span></h3>
                  <ul className="meds__list">
                    {groups[id].map(d => <DoseRow key={`${d.med_id}-${d.slot}`} dose={d} med={byId.get(d.med_id)} onToggle={onToggle} />)}
                  </ul>
                </section>
              ))}
            </section>

            <section className="meds__section" aria-labelledby="meds-all">
              <h2 id="meds-all" className="meds__h2">{t('meds.allMeds')}</h2>
              <ul className="meds__list">
                {meds.data.meds.map(m => (
                  <li key={m.id} className="medcard">
                    <p className="dose__name">{m.name}{m.strength && <span className="dose__strength"> {m.strength}</span>}</p>
                    {m.purpose && <p><span className="medcard__k">{t('meds.purpose')}:</span> {m.purpose}</p>}
                    {m.prescriber && (
                      <p className="medcard__line"><Stethoscope aria-hidden="true" strokeWidth={2} />
                        <span><span className="medcard__k">{t('meds.prescriber')}:</span> {m.prescriber}</span></p>
                    )}
                    {scheduleOf(m).length > 0 && <p className="tabular">{t('meds.times', { times: scheduleOf(m).map(x => slotTime(x, lang)).join(', ') })}</p>}
                    <RefillBadge med={m} />
                  </li>
                ))}
              </ul>
            </section>
          </>
        )}
    </div>
  )
}
