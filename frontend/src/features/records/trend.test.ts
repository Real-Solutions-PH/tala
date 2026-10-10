import { describe, expect, test } from 'vitest'
import { chartSummary, rangeFlag, sameUnit, trendBetween, trendOf } from './trend'
import { findHighlight } from './highlight'
import { obs } from './testing'

describe('trendOf', () => {
  test('up, down and same relative to the previous value', () => {
    expect(trendOf(118, 132)).toBe('up')
    expect(trendOf(7.2, 6.9)).toBe('down')
    expect(trendOf(130, 130)).toBe('same')
  })
  test('no previous value means no trend', () => {
    expect(trendOf(undefined, 132)).toBeNull()
    expect(trendOf(null, 132)).toBeNull()
  })
})

describe('rangeFlag', () => {
  test('flags only against the document reference range', () => {
    expect(rangeFlag(obs('fbs', 132, '2026-07-07'))).toBe('high')
    expect(rangeFlag(obs('fbs', 60, '2026-07-07'))).toBe('low')
    expect(rangeFlag(obs('fbs', 90, '2026-07-07'))).toBeNull()
    expect(rangeFlag(obs('fbs', 300, '2026-07-07', { ref_low: null, ref_high: null }))).toBeNull()
    expect(rangeFlag(obs('hdl', 35, '2026-07-07', { ref_low: 40, ref_high: null }))).toBe('low')
  })
})

describe('chartSummary', () => {
  const points = [obs('fbs', 118, '2024-07-02'), obs('fbs', 125, '2025-06-03'), obs('fbs', 130, '2026-03-02'), obs('fbs', 132, '2026-07-07')]
  test('reads like a sentence in English', () => {
    expect(chartSummary(points, 'FBS', 'en')).toBe('FBS rose from 118 to 132 mg/dL between July 2024 and July 2026')
  })
  test('and in Tagalog', () => {
    expect(chartSummary(points, 'FBS', 'tl')).toBe('Tumaas ang FBS mula 118 hanggang 132 mg/dL mula Hulyo 2024 hanggang Hulyo 2026')
  })
  test('falling and steady series', () => {
    const down = [obs('hba1c', 7.2, '2025-09-02'), obs('hba1c', 6.9, '2026-03-02')]
    expect(chartSummary(down, 'HbA1c', 'en')).toBe('HbA1c fell from 7.2 to 6.9 % between September 2025 and March 2026')
    const flat = [obs('fbs', 120, '2025-09-02'), obs('fbs', 120, '2026-03-02')]
    expect(chartSummary(flat, 'FBS', 'en')).toBe('FBS stayed at 120 mg/dL between September 2025 and March 2026')
  })
})

describe('findHighlight (VCAC-D-013)', () => {
  const md = '# Lab\n\n| Test | Result |\n|---|---|\n| FBS | 132 mg/dL |\n\nReleased 2026-07-07'
  test('finds match only when before + match + after appears verbatim', () => {
    const h = findHighlight(md, { before: '| FBS | ', match: '132 mg/dL', after: ' |' })
    expect(h).not.toBeNull()
    expect(md.slice(h!.start, h!.end)).toBe('132 mg/dL')
  })
  test('returns null when the context does not match verbatim', () => {
    expect(findHighlight(md, { before: '| HbA1c | ', match: '132 mg/dL', after: ' |' })).toBeNull()
    expect(findHighlight(md, { before: '', match: '', after: '' })).toBeNull()
    expect(findHighlight(null, { before: '', match: '132', after: '' })).toBeNull()
  })
})

describe('units (a trend never compares mg/dL with mmol/L)', () => {
  const mixed = [obs('fbs', 118, '2024-07-02'), obs('fbs', 7.1, '2025-06-03', { unit: 'mmol/L' }), obs('fbs', 132, '2026-07-07')]
  test('sameUnit keeps only the latest point\'s unit and says when others were left out', () => {
    const r = sameUnit(mixed)
    expect(r.points.map(p => p.value)).toEqual([118, 132])
    expect(r.mixed).toBe(true)
    expect(sameUnit([obs('fbs', 1, '2024-01-01'), obs('fbs', 2, '2024-02-01', { unit: ' MG/DL ' })]).mixed).toBe(false)
  })
  test('trendBetween is null across units and normal within one', () => {
    expect(trendBetween(mixed[1], mixed[2])).toBeNull()
    expect(trendBetween(mixed[0], mixed[2])).toBe('up')
    expect(trendBetween(undefined, mixed[2])).toBeNull()
  })
  test('chartSummary reads only same-unit points', () => {
    const mmolFirst = [obs('fbs', 6.1, '2023-01-10', { unit: 'mmol/L' }), ...mixed]
    expect(chartSummary(mmolFirst, 'FBS', 'en')).toBe('FBS rose from 118 to 132 mg/dL between July 2024 and July 2026')
  })
})
