import { useState } from 'react'
import { useParams } from 'react-router'
import { ArrowDown, ArrowRight, ArrowUp, ChartLine, FlaskConical, Info, Table, TriangleAlert, type LucideIcon } from 'lucide-react'
import { useObservations } from '../../api/queries'
import type { Observation } from '../../api/types'
import { Badge } from '../../components/Badge'
import { Button } from '../../components/Button'
import { Card } from '../../components/Card'
import { DisplayTitle } from '../../components/DisplayTitle'
import { EmptyState } from '../../components/EmptyState'
import { ErrorState } from '../../components/ErrorState'
import { Skeleton } from '../../components/Skeleton'
import { formatDate, useLang, useT, type Lang } from '../../i18n'
import { useLock } from '../lock/useLock'
import { TrendChart } from './TrendChart'
import { chartSummary, num, rangeFlag, rangeText, sameUnit, shortName, TREND_WORD, trendBetween, type Trend } from './trend'
import './records.css'

const MIN_CHART_POINTS = 4

const TREND_ICON: Record<Trend, LucideIcon> = { up: ArrowUp, down: ArrowDown, same: ArrowRight }

function TrendWord({ trend }: { trend: Trend | null }) {
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

function RangeBadge({ flag }: { flag: 'high' | 'low' | null }) {
  const t = useT()
  if (!flag) return null
  return <Badge tone="warn" icon={TriangleAlert}>{t(flag === 'high' ? 'records.highForRange' : 'records.lowForRange')}</Badge>
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
                  {asTable ? <LabTable points={points} lang={lang} /> : <TrendChart points={points} name={name} label={chartSummary(points, name, lang)} tick={d => formatDate(d, lang, { month: 'short', year: '2-digit' })} />}
                  <Button size="lg" block icon={asTable ? ChartLine : Table} className="btn--cta" onClick={() => setAsTable(v => !v)}>
                    {asTable ? t('records.viewChart') : t('records.viewTable')}
                  </Button>
                </Card>
              )}
    </div>
  )
}
