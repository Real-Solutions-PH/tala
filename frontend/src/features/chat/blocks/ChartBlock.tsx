import { useState } from 'react'
import { CartesianGrid, Line, LineChart, ReferenceArea, ResponsiveContainer, XAxis, YAxis } from 'recharts'
import { formatDate, useLang, useT } from '../../../i18n'
import type { Of } from './types'

export function ChartBlock({ block }: { block: Of<'chart'> }) {
  const t = useT()
  const [lang] = useLang()
  const [table, setTable] = useState(false)
  const data = block.points.map(p => ({ ...p, label: formatDate(p.date, lang, { month: 'short', year: '2-digit' }) }))
  const hasRef = block.ref_low != null && block.ref_high != null
  return (
    <section className="cblock">
      <h3 className="cblock__title">{block.label}{block.unit ? ` (${block.unit})` : ''}</h3>
      {table ? (
        <table className="cblock__table">
          <tbody>
            {block.points.map(p => <tr key={p.date}><td>{formatDate(p.date, lang)}</td><td>{p.value}{block.unit ? ` ${block.unit}` : ''}</td></tr>)}
          </tbody>
        </table>
      ) : (
        <div className="cblock__chart" aria-hidden="true">
          <ResponsiveContainer width="100%" height={200}>
            <LineChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: -16 }}>
              <CartesianGrid stroke="var(--border)" vertical={false} />
              {hasRef && <ReferenceArea y1={block.ref_low!} y2={block.ref_high!} fill="var(--primary-soft)" fillOpacity={0.6} />}
              <XAxis dataKey="label" tick={{ fill: 'var(--muted)', fontSize: 14 }} />
              <YAxis tick={{ fill: 'var(--muted)', fontSize: 14 }} />
              <Line type="monotone" dataKey="value" stroke="var(--primary)" strokeWidth={3} dot={{ r: 4 }} isAnimationActive={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
      {hasRef && <p className="cblock__muted">{t('blocks.refRange', { range: `${block.ref_low}–${block.ref_high}` })}</p>}
      <button type="button" className="btn btn--ghost" onClick={() => setTable(v => !v)}>
        <span>{table ? t('blocks.chartView') : t('blocks.tableView')}</span>
      </button>
    </section>
  )
}
