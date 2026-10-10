import { useState } from 'react'
import { Link, useParams } from 'react-router'
import { ArrowLeft, ChartLine, FlaskConical, Info, Table } from 'lucide-react'
import {
  Bar, BarChart, CartesianGrid, Cell, LabelList, ReferenceArea, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import { useObservations } from '../../api/queries'
import type { Observation } from '../../api/types'
import { Button } from '../../components/Button'
import { Card } from '../../components/Card'
import { DisplayTitle } from '../../components/DisplayTitle'
import { EmptyState } from '../../components/EmptyState'
import { ErrorState } from '../../components/ErrorState'
import { Skeleton } from '../../components/Skeleton'
import { formatDate, useLang, useT, type Lang } from '../../i18n'
import { useLock } from '../lock/useLock'
import { RangeBadge, TrendWord } from './HealthSummary'
import { chartSummary, num, rangeFlag, rangeText, sameUnit, shortName, trendBetween } from './trend'
import './records.css'

const MIN_CHART_POINTS = 4

/** Round axis ends and about four even ticks on 1/2/2.5/5 steps, so labels read 60, 80, 100 and not 142, 110, 85. */
export function niceAxis(min: number, max: number): { domain: [number, number]; ticks: number[] } {
  const span = Math.max(max - min, 1)
  const raw = (span * 1.2) / 4
  const mag = 10 ** Math.floor(Math.log10(raw))
  const step = [1, 2, 2.5, 5, 10].map(m => m * mag).find(x => x >= raw) ?? 10 * mag
  const lo = Math.floor((min - span * 0.1) / step) * step
  const hi = Math.ceil((max + span * 0.1) / step) * step
  const ticks: number[] = []
  for (let v = lo; v <= hi + step / 2; v += step) ticks.push(Number(v.toFixed(6)))
  return { domain: [lo, hi], ticks }
}

function LabTable({ points, lang }: { points: Observation[]; lang: Lang }) {
  const t = useT()
  // The range column only earns its place when the documents printed different ranges; else it is above.
  const ranges = new Set(points.map(p => rangeText(p.ref_low, p.ref_high, lang)))
  const showRange = ranges.size > 1
  return (
    <div className="lab-table-wrap">
      <table className="lab-table">
        <thead>
          <tr><th scope="col">{t('records.colDate')}</th><th scope="col">{t('records.colResult')}</th>{showRange && <th scope="col">{t('records.colRange')}</th>}</tr>
        </thead>
        <tbody>
          {[...points].reverse().map(p => (
            <tr key={p.id}>
              <td><time dateTime={p.date}>{formatDate(p.date, lang)}</time></td>
              <td>
                <span className="lab-table__value">{p.value != null ? num(p.value, lang) : p.value_text} {p.unit}</span>
                <RangeBadge flag={rangeFlag(p)} />
              </td>
              {showRange && <td>{rangeText(p.ref_low, p.ref_high, lang) ?? '—'}</td>}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function StatCards({ points, lang }: { points: Observation[]; lang: Lang }) {
  const t = useT()
  return (
    <>
      <p className="muted">{t('records.fewPoints')}</p>
      <ul className="stat-cards">
        {points.map((p, i) => ({ p, prev: points[i - 1] })).reverse().map(({ p, prev }) => (
          <li key={p.id}>
            <Card className="stat-card">
              <span className="stat-card__value"><span className="num">{p.value != null ? num(p.value, lang) : p.value_text}</span> <span className="stat-tile__unit">{p.unit}</span></span>
              <time className="small muted" dateTime={p.date}>{formatDate(p.date, lang)}</time>
              {prev && <TrendWord trend={trendBetween(prev, p)} />}
              <RangeBadge flag={rangeFlag(p)} />
            </Card>
          </li>
        ))}
      </ul>
    </>
  )
}

function Chart({ points, name, lang }: { points: Observation[]; name: string; lang: Lang }) {
  const last = points[points.length - 1]
  const lo = last.ref_low
  const hi = last.ref_high
  const values = points.map(p => p.value!)
  const min = Math.min(...values, lo ?? Infinity)
  const max = Math.max(...values, hi ?? -Infinity)
  const { domain, ticks } = niceAxis(min, max)
  const data = points.map(p => ({ date: p.date, value: p.value }))
  const tick = (d: string) => formatDate(d, lang, { month: 'short', year: '2-digit' })

  return (
    <figure className="lab-chart" role="img" aria-label={chartSummary(points, name, lang)}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 28, right: 12, bottom: 8, left: 4 }} accessibilityLayer={false} barCategoryGap="30%">
          <CartesianGrid vertical={false} />
          {(lo != null || hi != null) && <ReferenceArea y1={lo ?? domain[0]} y2={hi ?? domain[1]} ifOverflow="hidden" />}
          <XAxis dataKey="date" tickFormatter={tick} interval="preserveStartEnd" minTickGap={24} tickLine={false} tickMargin={8} />
          <YAxis domain={domain} ticks={ticks} interval={0} width={56} tickLine={false} axisLine={false} tickFormatter={v => num(v, lang)}
            label={{ value: last.unit ?? '', angle: -90, position: 'insideLeft', offset: 10, className: 'lab-chart__unit' }} />
          <Tooltip labelFormatter={d => formatDate(String(d), lang)} formatter={v => [`${num(Number(v), lang)} ${last.unit ?? ''}`, name]}
            isAnimationActive={false} />
          {/* Capsule bars, after the reference's Blood Pressure card; the latest reading is the highlighted one. */}
          <Bar dataKey="value" barSize={10} radius={[999, 999, 999, 999]} isAnimationActive={false}>
            {data.map((_, i) => <Cell key={i} className={i === data.length - 1 ? 'lab-chart__bar is-last' : 'lab-chart__bar'} />)}
            <LabelList dataKey="value" content={(p: { x?: number | string; y?: number | string; width?: number | string; index?: number; value?: unknown }) =>
              p.index === data.length - 1
                ? <text x={Number(p.x) + Number(p.width ?? 0) / 2} y={Number(p.y) - 12} textAnchor="middle" className="lab-chart__last">{num(Number(p.value), lang)}</text>
                : null} />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </figure>
  )
}

/** One lab over time: a chart with the normal range as a band (or stat cards below 4 results) and a table view. */
export function LabDetail() {
  const t = useT()
  const [lang] = useLang()
  const { code = '' } = useParams()
  const { profileId } = useLock()
  const q = useObservations(profileId, code)
  const [asTable, setAsTable] = useState(false)

  // Only the latest unit is compared, plotted and banded; results in another unit are left out with a notice.
  const { points, mixed } = sameUnit((q.data ?? []).filter(o => o.status !== 'proposed' && o.value != null))
  const label = points[points.length - 1]?.label
  const name = shortName(code, label, lang)
  const last = points[points.length - 1]
  const range = last ? rangeText(last.ref_low, last.ref_high, lang) : null
  const rangeLine = range && (
    <p className="lab-card__range"><span className="lab-card__swatch" aria-hidden="true" />{t('blocks.refRange', { range: `${range} ${last.unit ?? ''}`.trim() })}</p>
  )

  const unitNotice = mixed && <p className="unit-notice small"><Info aria-hidden="true" strokeWidth={2} /><span>{t('records.otherUnits')}</span></p>

  return (
    <div className="page lab">
      <Link to="/records" className="back-link" title={t('records.title')}><ArrowLeft aria-hidden="true" /><span className="sr-only">{t('records.title')}</span></Link>
      <DisplayTitle>{name === code && !label ? t('records.labs') : name}</DisplayTitle>
      {label && label !== name && <p className="muted">{label}</p>}

      {q.isPending
        ? <Skeleton height={280} radius={20} />
        : q.isError
          ? <ErrorState onRetry={() => { q.refetch() }} />
          : points.length === 0
            ? <EmptyState icon={FlaskConical} title={t('records.labEmptyTitle')} body={t('records.labEmptyBody')} />
            : points.length < MIN_CHART_POINTS
              ? <>{rangeLine}{unitNotice}<StatCards points={points} lang={lang} /></>
              : (
                <Card className="lab-card">
                  {rangeLine}
                  {unitNotice}
                  {asTable ? <LabTable points={points} lang={lang} /> : <Chart points={points} name={name} lang={lang} />}
                  <Button size="lg" block icon={asTable ? ChartLine : Table} onClick={() => setAsTable(v => !v)}>
                    {asTable ? t('records.viewChart') : t('records.viewTable')}
                  </Button>
                </Card>
              )}
    </div>
  )
}
