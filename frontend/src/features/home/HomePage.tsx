// Home, a copy of the prototype's: a status headline, the next-medicine panel with "Mark as taken", the Ask
// Kapiling pill, three quick actions, the latest results, and the "stays on this phone" line.
import { useMemo } from 'react'
import { Link } from 'react-router'
import { Check, CloudSun, FileText, HeartPulse, IdCard, Lock, Mic, Moon, Sun, TriangleAlert, type LucideIcon } from 'lucide-react'
import { useCards, useMeds, useSummary } from '../../api/queries'
import type { Observation } from '../../api/types'
import { Skeleton } from '../../components/Skeleton'
import { formatDate, useLang, useT, type Key } from '../../i18n'
import { useLock } from '../lock/useLock'
import { localDate, periodOf, slotTime, useToggleDose, type Dose, type Period } from '../meds/doses'
import { num, rangeFlag } from '../records/trend'
import './home.css'

const SLOT: Record<Period, [Key, LucideIcon]> = { morning: ['meds.morning', Sun], noon: ['meds.noon', CloudSun], night: ['meds.night', Moon] }

/** One latest result: name and its source on the left; the value and a worded chip on the right. */
function Result({ label, o, value, to, source }: { label: Key; o?: Observation; value: string; to: string; source: Key }) {
  const t = useT()
  const [lang] = useLang()
  if (!o) return null
  const flag = rangeFlag(o)
  return (
    <Link to={to} className="res">
      <span className="res__k">{t(label)}</span>
      <span className="res__src">{formatDate(o.date, lang, { month: 'short', day: 'numeric' })} · {t(source)}</span>
      <span className="res__v">
        <b className="num">{value}<small>{o.unit}</small></b>
        {flag
          ? <span className="chip-s c-warn"><TriangleAlert aria-hidden="true" strokeWidth={3} />{t(flag === 'high' ? 'home.aboveRange' : 'home.belowRange')}</span>
          : <span className="chip-s c-ok"><Check aria-hidden="true" strokeWidth={3} />{t('home.inRange')}</span>}
      </span>
    </Link>
  )
}

export function HomePage() {
  const t = useT()
  const [lang] = useLang()
  const { profileId } = useLock()
  const date = useMemo(() => localDate(), [])
  const meds = useMeds(profileId, date)
  const summary = useSummary(profileId)
  const cards = useCards(profileId)
  const onTake = useToggleDose(profileId, date, meds.data)

  const doses = (meds.data?.today ?? []) as Dose[]
  const done = doses.filter(d => d.taken_at != null).length
  const next = doses.find(d => d.taken_at == null)
  const byId = new Map((meds.data?.meds ?? []).map(m => [m.id, m]))
  const medOf = (d: Dose) => byId.get(d.med_id)
  const headline = doses.length && !next ? t('home.allTaken') : t('home.headline', { taken: done, total: doses.length })

  const philhealth = cards.data?.find(c => c.kind === 'philhealth')
  const latest = summary.data?.latest ?? {}
  const ok = (o?: Observation) => (o && o.status !== 'proposed' ? o : undefined)
  const fmt = (o?: Observation) => (o?.value != null ? num(o.value, lang) : o?.value_text ?? '')
  const bpS = ok(latest.bp_systolic)
  const bpD = ok(latest.bp_diastolic)

  const nextMed = next && medOf(next)
  const [slotWord, SlotIcon] = next ? SLOT[periodOf(next.slot)] : SLOT.morning

  return (
    <div className="page home">
      <div className="status"><h1 className="h">{headline}</h1></div>

      {meds.isPending ? <Skeleton height={220} radius={16} /> : doses.length > 0 && (
        <section className="panel nextcard" aria-labelledby="next-label">
          {next ? (
            <>
              <div className="row1">
                <span id="next-label" className="lbl">{t('home.nextMed')}</span>
                <span className="chip-s c-blue"><SlotIcon aria-hidden="true" strokeWidth={2} />{t(slotWord)}</span>
              </div>
              <div>
                <div className="drug">{next.name ?? nextMed?.name} {next.strength ?? nextMed?.strength}</div>
                <div className="note">{[slotTime(next.slot, lang), nextMed?.purpose].filter(Boolean).join(' · ')}</div>
              </div>
            </>
          ) : (
            <>
              <div className="row1">
                <span id="next-label" className="lbl">{t('meds.todayTitle')}</span>
                <span className="chip-s c-ok"><Check aria-hidden="true" strokeWidth={3} />{t('common.done')}</span>
              </div>
              <div className="drug">{t('home.allTaken')}</div>
            </>
          )}
          <div className="segs" aria-hidden="true">{doses.map((d, i) => <i key={i} className={d.taken_at != null ? 'on' : undefined} />)}</div>
          <div className="segcap">{t('home.doses', { taken: done, total: doses.length })}</div>
          {next
            ? <button type="button" className="btn btn--primary btn--block btn--lg" onClick={() => onTake(next)}><Check aria-hidden="true" strokeWidth={3} /><span>{t('home.markTaken')}</span></button>
            : <Link to="/meds" className="btn btn--ink btn--block btn--lg"><span>{t('home.seeMeds')}</span></Link>}
        </section>
      )}

      <Link to="/usap" className="askbig">
        <span className="mc" aria-hidden="true"><Mic strokeWidth={2} /></span>
        <span><b>{t('home.ask')}</b><span className="s">{t('home.askSub')}</span></span>
      </Link>

      <nav className="qa" aria-label={t('home.quick')}>
        <Link to={philhealth ? `/cards/${philhealth.id}` : '/cards'}><span className="qi" aria-hidden="true"><IdCard /></span>PhilHealth</Link>
        <Link to="/records"><span className="qi" aria-hidden="true"><FileText /></span>{t('nav.records')}</Link>
        <Link to={`/emergency/${profileId}`} className="red"><span className="qi" aria-hidden="true"><HeartPulse /></span>{t('emergency.button')}</Link>
      </nav>

      <section className="sec" aria-labelledby="home-latest">
        <div className="sech">
          <h2 id="home-latest">{t('home.latest')}</h2>
          <Link to="/records" className="link">{t('common.seeAll')}</Link>
        </div>
        {summary.isPending ? <Skeleton height={200} radius={16} /> : (
          <div className="panel results">
            <Result label="records.tileBpLong" o={bpS} to="/records/labs/bp_systolic" source="home.checkup"
              value={bpS ? `${fmt(bpS)}${bpD && bpD.date === bpS.date ? `/${fmt(bpD)}` : ''}` : ''} />
            <Result label="records.tileFbsLong" o={ok(latest.fbs)} value={fmt(ok(latest.fbs))} to="/records/labs/fbs" source="home.fromLab" />
            <Result label="records.tileHba1cLong" o={ok(latest.hba1c)} value={fmt(ok(latest.hba1c))} to="/records/labs/hba1c" source="home.fromLab" />
          </div>
        )}
      </section>

      <p className="foot"><Lock aria-hidden="true" strokeWidth={2.4} /><span>{t('home.stays')}</span></p>
    </div>
  )
}
