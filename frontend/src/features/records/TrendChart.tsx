// The prototype's trend chart (chartSVG): a line over a soft area, the normal range as a green band, each point
// labelled with its value and month, the latest point filled. Plain SVG; the label summarises it for screen readers.
import type { Observation } from '../../api/types'
import { formatDate, useLang, useT } from '../../i18n'
import { niceAxis, num } from './trend'

const W = 320, H = 170, L = 34, R = 14, TOP = 18, B = 26

/** `label` overrides the spoken summary; `tick` formats the dates under the points (month by default). */
export function TrendChart({ points, name, label: given, tick }: { points: Observation[]; name: string; label?: string; tick?: (date: string) => string }) {
  const t = useT()
  const [lang] = useLang()
  const data = points.filter(p => p.value != null) as (Observation & { value: number })[]
  if (data.length === 0) return null
  const last = data[data.length - 1]
  const lo = last.ref_low, hi = last.ref_high
  const vals = data.map(d => d.value)
  const { domain: [min, max], ticks } = niceAxis(Math.min(...vals, lo ?? Infinity), Math.max(...vals, hi ?? -Infinity))
  const x = (i: number) => L + (W - L - R) * (data.length === 1 ? 0.5 : i / (data.length - 1))
  const y = (v: number) => TOP + (H - TOP - B) * (1 - (v - min) / (max - min))
  const pts = data.map((d, i) => `${x(i)},${y(d.value)}`)
  const area = `M${x(0)},${y(min)} L${pts.join(' L')} L${x(data.length - 1)},${y(min)}Z`
  const month = tick ?? ((d: string) => formatDate(d, lang, { month: 'short' }))
  const label = given ?? `${name}: ${data.map(d => `${month(d.date)} ${num(d.value, lang)}`).join(', ')} ${last.unit ?? ''}.`
    + (lo != null && hi != null ? ` ${t('records.normalBand', { lo: num(lo, lang), hi: num(hi, lang) })}.` : '')

  return (
    <svg className="trend-chart" viewBox={`0 0 ${W} ${H}`} role="img" aria-label={label}>
      {lo != null && hi != null && <rect className="band" x={L} y={y(Math.min(hi, max))} width={W - L - R} height={y(Math.max(lo, min)) - y(Math.min(hi, max))} />}
      {ticks.map(v => (
        <g key={v}>
          <line className="grid" x1={L} x2={W - R} y1={y(v)} y2={y(v)} />
          <text className="ax" x={L - 6} y={y(v) + 3.5} textAnchor="end">{v}</text>
        </g>
      ))}
      {lo != null && hi != null && <text className="bl" x={L + 6} y={y(Math.max(lo, min)) - 5}>{t('records.normalBand', { lo: num(lo, lang), hi: num(hi, lang) })}</text>}
      <path className="area" d={area} />
      <polyline className="ln" points={pts.join(' ')} />
      {data.map((d, i) => {
        const isLast = i === data.length - 1
        return (
          <g key={d.id}>
            <circle className={isLast ? 'pt last' : 'pt'} cx={x(i)} cy={y(d.value)} r={isLast ? 5 : 3.5} />
            <text className="vl" x={x(i)} y={y(d.value) - 10} textAnchor="middle">{num(d.value, lang)}</text>
            <text className="ax" x={x(i)} y={H - 8} textAnchor="middle">{month(d.date)}</text>
          </g>
        )
      })}
    </svg>
  )
}
