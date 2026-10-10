import { useState } from 'react'
import { Camera } from 'lucide-react'
import { useObservations, useSummary } from '../../api/queries'
import { formatDate, useLang, useT } from '../../i18n'
import { useLock } from '../lock/useLock'
import { Timeline } from './Timeline'
import { TrendChart } from './TrendChart'
import { num, rangeFlag, sameUnit, TREND_WORD, trendBetween } from './trend'
import { UploadSheet } from './UploadSheet'
import './records.css'

function ageOf(birth: string): number {
  const b = new Date(birth), n = new Date()
  return n.getFullYear() - b.getFullYear() - (n < new Date(n.getFullYear(), b.getMonth(), b.getDate()) ? 1 : 0)
}

/** The FBS trend, as in the prototype: a title with the trend word, a Chart / Table switch, and the chart or table. */
function SugarTrend() {
  const t = useT()
  const [lang] = useLang()
  const { profileId } = useLock()
  const q = useObservations(profileId, 'fbs')
  const [view, setView] = useState<'chart' | 'table'>('chart')
  const { points } = sameUnit((q.data ?? []).filter(o => o.status !== 'proposed' && o.value != null))
  if (points.length === 0) return null
  const last = points[points.length - 1]
  const trend = trendBetween(points[points.length - 2], last)
  const high = rangeFlag(last) === 'high'

  return (
    <section className="sec" aria-labelledby="trend-title">
      <div className="sech">
        <h2 id="trend-title">{t('records.trendTitle')}</h2>
        {trend && <span className={`chip-s ${trend === 'up' && high ? 'c-warn' : 'c-ok'}`}>{t(TREND_WORD[trend])}</span>}
      </div>
      <div className="seg" role="group" aria-label={t('records.trendTitle')}>
        <button type="button" aria-pressed={view === 'chart'} onClick={() => setView('chart')}>{t('records.chart')}</button>
        <button type="button" aria-pressed={view === 'table'} onClick={() => setView('table')}>{t('records.table')}</button>
      </div>
      <div className="panel chart">
        {view === 'chart' ? <TrendChart points={points} name="FBS" /> : (
          <table className="t">
            <thead><tr><th>{t('records.tableDate')}</th><th>FBS {last.unit}</th><th>{t('records.tableRange')}</th></tr></thead>
            <tbody>{points.slice().reverse().map(p => {
              const f = rangeFlag(p)
              return (
                <tr key={p.id}>
                  <td>{formatDate(p.date, lang, { month: 'short', day: 'numeric', year: 'numeric' })}</td>
                  <td><b>{num(p.value!, lang)}</b></td>
                  <td><span className={`chip-s ${f ? 'c-warn' : 'c-ok'}`}>{t(f === 'high' ? 'records.high' : f === 'low' ? 'records.low' : 'records.normal')}</span></td>
                </tr>
              )
            })}</tbody>
          </table>
        )}
      </div>
    </section>
  )
}

/** Records, a copy of the prototype's: who it is, the scan tile, the blood sugar trend and the timeline. */
export function RecordsPage() {
  const t = useT()
  const { profileId } = useLock()
  const profile = useSummary(profileId).data?.profile
  const [adding, setAdding] = useState(false)
  return (
    <div className="page records">
      <div className="greet">
        <h1 className="h">{t('nav.records')}</h1>
        {profile?.birth_date && <p className="sub">{t('records.personLine', { name: profile.full_name, age: ageOf(profile.birth_date), blood: profile.blood_type ?? '—' })}</p>}
      </div>
      <button type="button" className="scanbtn" aria-label={t('records.addResult')} aria-describedby="scan-sub" onClick={() => setAdding(true)}>
        <Camera aria-hidden="true" strokeWidth={2} />
        <span><b>{t('records.scan')}</b><span id="scan-sub">{t('records.scanSub')}</span></span>
      </button>
      <SugarTrend />
      <Timeline />
      <UploadSheet open={adding} onClose={() => setAdding(false)} />
    </div>
  )
}
