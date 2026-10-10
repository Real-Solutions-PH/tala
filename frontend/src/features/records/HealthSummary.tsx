import { Link } from 'react-router'
import { ArrowDown, ArrowRight, ArrowUp, Droplet, FlaskConical, HeartPulse, TriangleAlert, type LucideIcon } from 'lucide-react'
import { useObservations, useProfiles, useSummary } from '../../api/queries'
import type { Observation } from '../../api/types'
import { Badge } from '../../components/Badge'
import { Card } from '../../components/Card'
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

function Tile({ name, icon: Icon, to, latest, value, series, flag }: TileProps) {
  const t = useT()
  const [lang] = useLang()
  if (!latest) {
    return (
      <div className="stat-tile stat-tile--empty">
        <span className="stat-tile__head"><span className="stat-tile__icon" aria-hidden="true"><Icon /></span></span>
        <span className="stat-tile__name">{t(name)}</span>
        <span className="stat-tile__none">{t('records.noResultYet')}</span>
      </div>
    )
  }
  // After the reference tile: icon top-left, the reading small top-right, the name large bottom-left.
  return (
    <Link to={to} className="stat-tile">
      <span className="stat-tile__head">
        <span className="stat-tile__icon" aria-hidden="true"><Icon /></span>
        <span className="stat-tile__now">
          <time className="stat-tile__date" dateTime={latest.date}>{formatDate(latest.date, lang, { month: 'short', day: 'numeric' })}<span className="sr-only">, {latest.date.slice(0, 4)}</span></time>
          <span className="stat-tile__value"><span className="num">{value}</span> <span className="stat-tile__unit">{latest.unit}</span></span>
          {flag && <span className="stat-tile__flag" aria-hidden="true"><TriangleAlert />{t(flag === 'high' ? 'blocks.high' : 'blocks.low')}</span>}
        </span>
      </span>
      <span className="stat-tile__name">{t(name)}</span>
      {series && <span className="sr-only"><TrendWord trend={trendBetween(previous(series, latest), latest)} /></span>}
      {flag && <span className="sr-only"><RangeBadge flag={flag} /></span>}
    </Link>
  )
}

/** The "Kalagayan" block: conditions, allergies, and the latest BP, FBS and HbA1c with a trend word. */
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
    return <Card as="section" className="summary"><Skeleton height={28} width="50%" /><Skeleton height={96} /><Skeleton height={96} /></Card>
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

  return (
    <Card as="section" className="summary" aria-labelledby="summary-title">
      <h2 id="summary-title">{t('records.summary')}</h2>

      <div className="summary__group">
        <h3>{t('records.conditions')}</h3>
        {conditions.length
          ? <ul className="summary__list">{conditions.map(c => <li key={c.id}>{c.name}</li>)}</ul>
          : <p className="muted">{t('records.noConditions')}</p>}
      </div>

      <div className="summary__group">
        <h3>{t('records.allergies')}</h3>
        {s.allergies.length
          ? <ul className="summary__badges">{s.allergies.map(a => (
              <li key={a.id}><Badge tone="danger" icon={TriangleAlert}>{a.substance}{a.reaction ? ` · ${a.reaction}` : ''}</Badge></li>
            ))}</ul>
          : <p className="muted">{t('records.noAllergies')}</p>}
      </div>

      <div className="summary__group">
        <h3>{t('records.latestResults')}</h3>
        <div className="panel__top">
          <span className="name-pill">
            {me?.photo_url ? <img src={me.photo_url} alt="" width={44} height={44} /> : <span className="name-pill__dot" aria-hidden="true" />}
            <span>{me ? (me.nickname ?? me.full_name) : ''}</span>
          </span>
        </div>
        <div className="stat-grid">
          {/* BP's trend follows the systolic (top) number */}
          <Tile name="records.tileBp" icon={HeartPulse} to="/records/labs/bp_systolic" latest={bpS} series={confirmed(sys.data)} flag={bpFlag}
            value={bpS ? `${fmt(bpS)}${bpD && bpD.date === bpS.date ? `/${fmt(bpD)}` : ''}` : undefined} />
          <Tile name="records.tileFbs" icon={Droplet} to="/records/labs/fbs" latest={latest.fbs} value={fmt(latest.fbs)}
            series={confirmed(fbs.data)} flag={latest.fbs ? rangeFlag(latest.fbs) : null} />
          <Tile name="records.tileHba1c" icon={FlaskConical} to="/records/labs/hba1c" latest={latest.hba1c} value={fmt(latest.hba1c)}
            series={confirmed(a1c.data)} flag={latest.hba1c ? rangeFlag(latest.hba1c) : null} />
          <div className="stat-tile stat-tile--static">
            <span className="stat-tile__head">
              <span className="stat-tile__icon stat-tile__icon--danger" aria-hidden="true"><TriangleAlert /></span>
              <span className="stat-tile__now"><span className="stat-tile__value"><span className="num">{s.allergies.length}</span></span></span>
            </span>
            <span className="stat-tile__name">{t('records.allergies')}</span>
          </div>
        </div>
      </div>
    </Card>
  )
}
