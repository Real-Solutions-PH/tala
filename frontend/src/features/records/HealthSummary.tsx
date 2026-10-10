import { Link } from 'react-router'
import { ArrowDown, ArrowRight, ArrowUp, ChevronRight, Droplet, FlaskConical, HeartPulse, ShieldAlert, Stethoscope, TriangleAlert, type LucideIcon } from 'lucide-react'
import { useObservations, useProfiles, useSummary } from '../../api/queries'
import type { Observation } from '../../api/types'
import { Badge } from '../../components/Badge'
import { ErrorState } from '../../components/ErrorState'
import { Skeleton } from '../../components/Skeleton'
import { formatDate, useLang, useT, type Key } from '../../i18n'
import { useLock } from '../lock/useLock'
import { num, rangeFlag, sameUnitAs, TREND_WORD, trendBetween, type Trend } from './trend'
import './records.css'

const TREND_ICON: Record<Trend, LucideIcon> = { up: ArrowUp, down: ArrowDown, same: ArrowRight }

export function TrendWord({ trend }: { trend: Trend | null }) {
  const t = useT()
  if (!trend) return <span className="trend trend--none">{t('records.firstResult')}</span>
  const Icon = TREND_ICON[trend]
  return (
    <span className="trend">
      <Icon aria-hidden="true" strokeWidth={2.25} />
      <span>{t(TREND_WORD[trend])}</span>
    </span>
  )
}

export function RangeBadge({ flag }: { flag: 'high' | 'low' | null }) {
  const t = useT()
  if (!flag) return null
  return <Badge tone="warn" icon={TriangleAlert}>{t(flag === 'high' ? 'records.highForRange' : 'records.lowForRange')}</Badge>
}

/**
 * Confirmed values only, oldest first: unconfirmed (proposed) values never reach the summary. Undefined while the
 * series is loading or failed, so the tile shows no trend rather than a wrong "first result".
 */
const confirmed = (xs: Observation[] | undefined) => xs?.filter(o => o.status !== 'proposed')
/** The value before `latest` in the same unit (a result in another unit is never compared). */
const previous = (series: Observation[], latest: Observation) => {
  const i = series.findIndex(o => o.id === latest.id)
  const before = (i >= 0 ? series.slice(0, i) : series.filter(o => o.date < latest.date)).filter(o => sameUnitAs(o, latest))
  return before[before.length - 1]
}

type TileProps = { name: Key; icon: LucideIcon; to: string; latest?: Observation; value?: string; series?: Observation[]; flag: 'high' | 'low' | null }

/** One vital, read top to bottom on the left: icon and label, the value, the status words, the date. */
function Tile({ name, icon: Icon, to, latest, value, series, flag }: TileProps) {
  const t = useT()
  const [lang] = useLang()
  const head = (
    <span className="vtile__head">
      <span className="vtile__icon" aria-hidden="true"><Icon /></span>
      {latest && <ChevronRight className="vtile__go" aria-hidden="true" />}
    </span>
  )
  const label = <span className="vtile__label">{t(name)}</span>
  if (!latest) {
    return (
      <div className="vtile vtile--empty">
        {head}
        {label}
        <span className="vtile__none">{t('records.noResultYet')}</span>
      </div>
    )
  }
  return (
    <Link to={to} className="vtile">
      {head}
      {label}
      <span className="vtile__value"><span className="num">{value}</span> <span className="vtile__unit">{latest.unit}</span></span>
      {(flag || series) && (
        <span className="vtile__status">
          <RangeBadge flag={flag} />
          {series && <TrendWord trend={trendBetween(previous(series, latest), latest)} />}
        </span>
      )}
      <time className="vtile__date" dateTime={latest.date}>{formatDate(latest.date, lang, { month: 'short', day: 'numeric', year: 'numeric' })}</time>
    </Link>
  )
}

/** The "Kalagayan" block: the latest BP, FBS and HbA1c with a trend word, then allergies and conditions. */
export function HealthSummary() {
  const t = useT()
  const [lang] = useLang()
  const { profileId } = useLock()
  const summary = useSummary(profileId)
  const fbs = useObservations(profileId, 'fbs')
  const a1c = useObservations(profileId, 'hba1c')
  const sys = useObservations(profileId, 'bp_systolic')
  const me = useProfiles().data?.find(p => p.id === profileId)

  if (summary.isPending) {
    return <section className="summary"><Skeleton height={24} width="40%" /><Skeleton height={340} radius={20} /><Skeleton height={140} radius={20} /></section>
  }
  if (summary.isError) return <ErrorState onRetry={() => { summary.refetch() }} />

  const s = summary.data
  const latest = Object.fromEntries(Object.entries(s.latest).filter(([, o]) => o.status !== 'proposed'))
  const conditions = s.conditions.filter(c => c.status === 'active')
  const bpS = latest.bp_systolic
  const bpD = latest.bp_diastolic
  const bpFlag = bpS && (rangeFlag(bpS) === 'high' || (bpD && rangeFlag(bpD) === 'high')) ? 'high'
    : bpS && (rangeFlag(bpS) === 'low' || (bpD && rangeFlag(bpD) === 'low')) ? 'low' : null
  const fmt = (o?: Observation) => (o?.value != null ? num(o.value, lang) : o?.value_text ?? '')
  const who = me ? (me.nickname ?? me.full_name) : ''

  return (
    <section className="summary" aria-labelledby="summary-title">
      <h2 id="summary-title">{t('records.summary')}</h2>

      {/* The reference's blue panel: a white name pill, then the vitals as lighter-blue tiles. */}
      <div className="vpanel">
        {who && (
          <p className="vpanel__pill">
            {me?.photo_url ? <img className="vpanel__avatar" src={me.photo_url} alt="" /> : null}
            <span>{t('records.summaryOf', { name: who })}</span>
          </p>
        )}
        <div className="vgrid">
          {/* BP's trend follows the systolic (top) number */}
          <Tile name="records.tileBpLong" icon={HeartPulse} to="/records/labs/bp_systolic" latest={bpS} series={confirmed(sys.data)} flag={bpFlag}
            value={bpS ? `${fmt(bpS)}${bpD && bpD.date === bpS.date ? `/${fmt(bpD)}` : ''}` : undefined} />
          <Tile name="records.tileFbsLong" icon={Droplet} to="/records/labs/fbs" latest={latest.fbs} value={fmt(latest.fbs)}
            series={confirmed(fbs.data)} flag={latest.fbs ? rangeFlag(latest.fbs) : null} />
          <Tile name="records.tileHba1cLong" icon={FlaskConical} to="/records/labs/hba1c" latest={latest.hba1c} value={fmt(latest.hba1c)}
            series={confirmed(a1c.data)} flag={latest.hba1c ? rangeFlag(latest.hba1c) : null} />
        </div>
      </div>

      <div className="stile stile--allergy">
        <h3 className="stile__label"><span className="vtile__icon vtile__icon--danger" aria-hidden="true"><ShieldAlert /></span>{t('records.allergiesTitle')}</h3>
        {s.allergies.length
          ? <ul className="allergy-list">{s.allergies.map(a => (
              <li key={a.id}>
                <Badge tone="danger" icon={TriangleAlert}>{a.substance}</Badge>
                {a.reaction && <span className="muted">{a.reaction}</span>}
              </li>
            ))}</ul>
          : <p className="muted">{t('records.noAllergiesRecorded')}</p>}
      </div>

      <div className="stile">
        <h3 className="stile__label"><span className="vtile__icon" aria-hidden="true"><Stethoscope /></span>{t('records.conditions')}</h3>
        {conditions.length
          ? <ul className="summary__list">{conditions.map(c => <li key={c.id}>{c.name}</li>)}</ul>
          : <p className="muted">{t('records.noConditions')}</p>}
      </div>
    </section>
  )
}
