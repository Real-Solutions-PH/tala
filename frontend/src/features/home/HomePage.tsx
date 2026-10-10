// Home, after the prototype: today's medicines at a glance with the next dose and one "Markahang nainom" action,
// the Ask Kapiling pill, three quick actions (PhilHealth, Talaan, Emergency), the latest results, and a
// privacy line. Everything here is a shortcut into an existing screen.
import { useMemo, useState } from 'react'
import { Link } from 'react-router'
import { Check, ChevronRight, FileHeart, HeartPulse, IdCard, Lock, Mic, Plane, ShieldCheck, Stethoscope, TriangleAlert, UserRound, type LucideIcon } from 'lucide-react'
import { useCards, useMeds, useProfiles, useSummary } from '../../api/queries'
import type { Observation } from '../../api/types'
import { Badge } from '../../components/Badge'
import { Button } from '../../components/Button'
import { DisplayTitle } from '../../components/DisplayTitle'
import { Sheet } from '../../components/Sheet'
import { Skeleton } from '../../components/Skeleton'
import { formatDate, useLang, useT, type Key } from '../../i18n'
import { useLock } from '../lock/useLock'
import { localDate, periodOf, slotTime, useToggleDose, type Dose } from '../meds/doses'
import { num, rangeFlag } from '../records/trend'
import './home.css'

const PERIOD_WORD = { morning: 'meds.morning', noon: 'meds.noon', night: 'meds.night' } as const

/** The next untaken dose, with one bar per dose and the action that marks it. */
function NextDose({ doses, onTake, name }: { doses: Dose[]; onTake: (d: Dose) => void; name: (d: Dose) => string }) {
  const t = useT()
  const [lang] = useLang()
  const taken = doses.filter(d => d.taken_at != null).length
  const next = doses.find(d => d.taken_at == null)
  return (
    <section className="card nextdose" aria-labelledby="nextdose-label">
      <div className="nextdose__row">
        <span id="nextdose-label" className="nextdose__label">{t(next ? 'home.nextMed' : 'meds.todayHeading')}</span>
        {next
          ? <span className="nextdose__chip">{t(PERIOD_WORD[periodOf(next.slot)])} · {slotTime(next.slot, lang)}</span>
          : <Badge tone="ok" icon={Check}>{t('common.done')}</Badge>}
      </div>
      <p className="nextdose__drug">{next ? name(next) : t('home.allTaken')}</p>
      <div className="nextdose__segs" aria-hidden="true">{doses.map((d, i) => <i key={i} className={d.taken_at != null ? 'is-on' : undefined} />)}</div>
      <p className="nextdose__cap">{t('home.doses', { taken, total: doses.length })}</p>
      {next
        ? <Button size="lg" block icon={Check} onClick={() => onTake(next)}>{t('meds.markTaken')}</Button>
        : <Link to="/meds" className="btn btn--secondary btn--lg btn--block"><span>{t('home.seeMeds')}</span></Link>}
    </section>
  )
}

/** One latest result: name and date on the left, the value and its worded range on the right. */
function Result({ label, o, value, to }: { label: Key; o?: Observation; value: string; to: string }) {
  const t = useT()
  const [lang] = useLang()
  if (!o) return null
  const flag = rangeFlag(o)
  return (
    <li>
      <Link to={to} className="res">
        <span className="res__k">{t(label)}</span>
        <time className="res__d" dateTime={o.date}>{formatDate(o.date, lang, { month: 'short', day: 'numeric', year: 'numeric' })}</time>
        <span className="res__v">
          <b className="num">{value}<small>{o.unit}</small></b>
          {flag
            ? <Badge tone="warn" icon={TriangleAlert}>{t(flag === 'high' ? 'records.highForRange' : 'records.lowForRange')}</Badge>
            : <Badge tone="ok" icon={Check}>{t('home.inRange')}</Badge>}
        </span>
      </Link>
    </li>
  )
}

const TRUST: { icon: LucideIcon; title: Key; body: Key }[] = [
  { icon: Lock, title: 'home.trust1', body: 'home.trust1Body' },
  { icon: Plane, title: 'home.trust2', body: 'home.trust2Body' },
  { icon: UserRound, title: 'home.trust3', body: 'home.trust3Body' },
  { icon: Stethoscope, title: 'home.trust4', body: 'home.trust4Body' },
]

export function HomePage() {
  const t = useT()
  const [lang] = useLang()
  const { profileId } = useLock()
  const date = useMemo(() => localDate(), [])
  const meds = useMeds(profileId, date)
  const summary = useSummary(profileId)
  const cards = useCards(profileId)
  const me = useProfiles().data?.find(p => p.id === profileId)
  const onTake = useToggleDose(profileId, date, meds.data)
  const [trust, setTrust] = useState(false)

  const doses = (meds.data?.today ?? []) as Dose[]
  const taken = doses.filter(d => d.taken_at != null).length
  const byId = new Map((meds.data?.meds ?? []).map(m => [m.id, m]))
  const doseName = (d: Dose) => {
    const m = byId.get(d.med_id)
    return [d.name ?? m?.name, d.strength ?? m?.strength].filter(Boolean).join(' ')
  }
  const who = me ? (me.nickname ?? me.full_name) : ''
  const headline = doses.length === 0 ? t('home.noMeds', { name: who })
    : taken === doses.length ? t('home.allTaken') : t('home.headline', { taken, total: doses.length })

  const philhealth = cards.data?.find(c => c.kind === 'philhealth')
  const latest = summary.data?.latest ?? {}
  const ok = (o?: Observation) => (o && o.status !== 'proposed' ? o : undefined)
  const fmt = (o?: Observation) => (o?.value != null ? num(o.value, lang) : o?.value_text ?? '')
  const bpS = ok(latest.bp_systolic)
  const bpD = ok(latest.bp_diastolic)

  return (
    <div className="page home">
      <div className="home__head">
        <DisplayTitle>{headline}</DisplayTitle>
        <button type="button" className="trust-pill" onClick={() => setTrust(true)} aria-haspopup="dialog">
          <ShieldCheck aria-hidden="true" strokeWidth={2} /><span>{t('home.private')}</span>
        </button>
      </div>

      {meds.isPending ? <Skeleton height={260} radius={16} /> : doses.length > 0 && <NextDose doses={doses} onTake={onTake} name={doseName} />}

      <Link to="/usap" className="askpill">
        <span className="askpill__mic" aria-hidden="true"><Mic strokeWidth={2} /></span>
        <span className="askpill__text"><b>{t('home.ask')}</b><span>{t('home.askSub')}</span></span>
      </Link>

      <nav className="quick" aria-label={t('home.quick')}>
        <Link to={philhealth ? `/cards/${philhealth.id}` : '/cards'} className="quick__item">
          <span className="quick__icon" aria-hidden="true"><IdCard /></span>PhilHealth
        </Link>
        <Link to="/records" className="quick__item">
          <span className="quick__icon" aria-hidden="true"><FileHeart /></span>{t('nav.records')}
        </Link>
        <Link to={`/emergency/${profileId}`} className="quick__item quick__item--danger">
          <span className="quick__icon" aria-hidden="true"><HeartPulse /></span>{t('emergency.button')}
        </Link>
      </nav>

      <section className="home__sec" aria-labelledby="home-latest">
        <div className="home__sech">
          <h2 id="home-latest">{t('home.latest')}</h2>
          <Link to="/records" className="home__link">{t('common.seeAll')}<ChevronRight aria-hidden="true" /></Link>
        </div>
        {summary.isPending ? <Skeleton height={200} radius={16} /> : (
          <ul className="card results">
            <Result label="records.tileBpLong" o={bpS} to="/records/labs/bp_systolic"
              value={bpS ? `${fmt(bpS)}${bpD && bpD.date === bpS.date ? `/${fmt(bpD)}` : ''}` : ''} />
            <Result label="records.tileFbsLong" o={ok(latest.fbs)} value={fmt(ok(latest.fbs))} to="/records/labs/fbs" />
            <Result label="records.tileHba1cLong" o={ok(latest.hba1c)} value={fmt(ok(latest.hba1c))} to="/records/labs/hba1c" />
          </ul>
        )}
      </section>

      <p className="home__foot"><Lock aria-hidden="true" strokeWidth={2} /><span>{t('home.stays')}</span></p>

      <Sheet open={trust} onClose={() => setTrust(false)} title={t('home.trustTitle')}>
        <ul className="card trust-list">
          {TRUST.map(({ icon: Icon, title, body }) => (
            <li key={title}><Icon aria-hidden="true" strokeWidth={2} /><span><b>{t(title)}</b><span>{t(body)}</span></span></li>
          ))}
        </ul>
        <Button size="lg" block onClick={() => setTrust(false)}>{t('home.gotIt')}</Button>
      </Sheet>
    </div>
  )
}
