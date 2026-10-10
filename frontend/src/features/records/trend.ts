// Pure helpers for lab values: trend against the previous value, the reference-range flag, and the chart's
// one-sentence summary. No "good" or "bad" judgement beyond the range printed on the document.
import type { Observation } from '../../api/types'
import { formatDate, formatNumber, translate, type Key, type Lang } from '../../i18n'

export type Trend = 'up' | 'down' | 'same'

export function trendOf(prev: number | null | undefined, cur: number | null | undefined): Trend | null {
  if (prev == null || cur == null) return null
  return cur > prev ? 'up' : cur < prev ? 'down' : 'same'
}

/** Units compare loosely ("mg/dL" = " MG/DL "), but a different unit is never compared or plotted. */
const unitKey = (u: string | null | undefined) => (u ?? '').trim().toLowerCase()
export const sameUnitAs = (a: Pick<Observation, 'unit'>, b: Pick<Observation, 'unit'>) => unitKey(a.unit) === unitKey(b.unit)

/** The points (oldest first) that share the latest point's unit, and whether any were left out. */
export function sameUnit(points: Observation[]): { points: Observation[]; mixed: boolean } {
  const last = points[points.length - 1]
  if (!last) return { points, mixed: false }
  const kept = points.filter(p => sameUnitAs(p, last))
  return { points: kept, mixed: kept.length !== points.length }
}

/** Trend from one observation to the next; null when either is missing or their units differ. */
export function trendBetween(prev: Pick<Observation, 'value' | 'unit'> | undefined, cur: Pick<Observation, 'value' | 'unit'> | undefined): Trend | null {
  if (!prev || !cur || !sameUnitAs(prev, cur)) return null
  return trendOf(prev.value, cur.value)
}

export const TREND_WORD: Record<Trend, Key> = { up: 'records.rose', down: 'records.fell', same: 'records.same' }

export function rangeFlag(o: Pick<Observation, 'value' | 'ref_low' | 'ref_high'>): 'high' | 'low' | null {
  if (o.value == null) return null
  if (o.ref_high != null && o.value > o.ref_high) return 'high'
  if (o.ref_low != null && o.value < o.ref_low) return 'low'
  return null
}

/** Short names people already use for the common tests; anything else keeps the document's label. */
const SHORT: Record<string, Key> = { fbs: 'records.tileFbs', hba1c: 'records.tileHba1c' }
export function shortName(code: string, label: string | undefined, lang: Lang): string {
  return SHORT[code] ? translate(lang, SHORT[code]) : (label ?? code)
}

export const num = (v: number, lang: Lang) => formatNumber(v, lang, { maximumFractionDigits: 2 })

/** Readable range text such as "70–100", "≤ 200" or "≥ 40"; null when the document printed none. */
export function rangeText(lo: number | null, hi: number | null, lang: Lang): string | null {
  if (lo != null && hi != null) return `${num(lo, lang)}–${num(hi, lang)}`
  if (hi != null) return `≤ ${num(hi, lang)}`
  if (lo != null) return `≥ ${num(lo, lang)}`
  return null
}

/** "FBS rose from 118 to 132 mg/dL between July 2024 and July 2026" (points oldest first). */
export function chartSummary(points: Observation[], name: string, lang: Lang): string {
  const withValue = sameUnit(points.filter(p => p.value != null)).points
  if (withValue.length === 0) return name
  const first = withValue[0]
  const last = withValue[withValue.length - 1]
  const month = (d: string) => formatDate(d, lang, { month: 'long', year: 'numeric' })
  const key: Key = { up: 'records.chartRose', down: 'records.chartFell', same: 'records.chartSame' }[trendOf(first.value, last.value) ?? 'same'] as Key
  return translate(lang, key, {
    name, from: num(first.value!, lang), to: num(last.value!, lang), unit: last.unit ?? '',
    start: month(first.date), end: month(last.date),
  }).replace(/\s+/g, ' ').trim()
}
