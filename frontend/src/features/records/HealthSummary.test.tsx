import { cleanup, screen, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest'
import type { Observation } from '../../api/types'
import { HealthSummary } from './HealthSummary'
import { json, mockFetch, obs, renderRoutes } from './testing'

const SERIES: Record<string, Observation[]> = {
  fbs: [obs('fbs', 118, '2024-07-02'), obs('fbs', 132, '2026-07-07')],
  hba1c: [obs('hba1c', 7.2, '2025-09-02'), obs('hba1c', 6.9, '2026-03-02')],
  bp_systolic: [obs('bp_systolic', 140, '2026-03-02'), obs('bp_systolic', 140, '2026-07-07')],
  bp_diastolic: [obs('bp_diastolic', 86, '2026-03-02'), obs('bp_diastolic', 88, '2026-07-07')],
}
const last = (code: string) => SERIES[code][SERIES[code].length - 1]

function summary(latest: Record<string, Observation>) {
  return {
    profile: { id: 1, nickname: 'Lola Remy', full_name: 'Remedios Santos Dela Cruz' },
    conditions: [{ id: 1, name: 'Type 2 diabetes', since: '2019', status: 'active', notes: null },
      { id: 2, name: 'Old sprain', since: '2001', status: 'resolved', notes: null }],
    allergies: [{ id: 1, substance: 'Penicillin', reaction: 'Rash', severity: 'severe' }],
    meds: [], contacts: [],
    latest,
  }
}

function setup(latest: Record<string, Observation> = { fbs: last('fbs'), hba1c: last('hba1c'), bp_systolic: last('bp_systolic'), bp_diastolic: last('bp_diastolic') }) {
  mockFetch({
    'GET /api/profiles/1/summary': () => json(summary(latest)),
    'GET /api/profiles/1/observations': ({ url }) => json(SERIES[new URL(url, 'http://x').searchParams.get('code')!] ?? []),
  })
  return renderRoutes([{ path: '/records', element: <HealthSummary /> }], '/records')
}

beforeEach(() => localStorage.clear())
afterEach(() => { cleanup(); vi.unstubAllGlobals() })

describe('HealthSummary', () => {
  test('lists active conditions and allergies as red badges with an icon and a word', async () => {
    setup()
    expect(await screen.findByText('Type 2 diabetes')).toBeTruthy()
    expect(screen.queryByText('Old sprain')).toBeNull()
    const allergy = screen.getByText(/Penicillin/).closest('.badge')!
    expect(allergy.className).toContain('badge--danger')
    expect(allergy.querySelector('svg')).toBeTruthy()
  })

  test('tiles show value, unit, date and the trend word for up, down and same', async () => {
    setup()
    const fbs = await screen.findByRole('link', { name: /FBS/ })
    expect(fbs.textContent).toContain('132')
    expect(fbs.textContent).toContain('mg/dL')
    expect(fbs.textContent).toMatch(/2026/)
    expect(within(fbs).getByText('Tumaas')).toBeTruthy()
    expect(fbs.getAttribute('href')).toBe('/records/labs/fbs')

    const a1c = await screen.findByRole('link', { name: /HbA1c/ })
    expect(await within(a1c).findByText('Bumaba')).toBeTruthy()

    const bp = await screen.findByRole('link', { name: /BP/ })
    expect(bp.textContent).toContain('140/88')
    expect(await within(bp).findByText('Pareho')).toBeTruthy()
  })

  test('flags only against the document reference range', async () => {
    setup()
    const fbs = await screen.findByRole('link', { name: /FBS/ })
    expect(within(fbs).getByText('Mataas sa range')).toBeTruthy()
  })

  test('unconfirmed (proposed) values never reach the summary', async () => {
    setup({ fbs: obs('fbs', 999, '2026-08-01', { status: 'proposed' }) })
    await screen.findByText('Type 2 diabetes')
    expect(screen.queryByText(/999/)).toBeNull()
  })

  test('English trend words', async () => {
    mockFetch({
      'GET /api/profiles/1/summary': () => json(summary({ fbs: last('fbs') })),
      'GET /api/profiles/1/observations': () => json(SERIES.fbs),
    })
    renderRoutes([{ path: '/records', element: <HealthSummary /> }], '/records', 'en')
    const fbs = await screen.findByRole('link', { name: /FBS/ })
    expect(await within(fbs).findByText('Went up')).toBeTruthy()
    expect(within(fbs).getByText('High for the range')).toBeTruthy()
  })
})

describe('HealthSummary when a series fails', () => {
  test('shows no trend word rather than a wrong one', async () => {
    mockFetch({
      'GET /api/profiles/1/summary': () => json(summary({ fbs: last('fbs') })),
      'GET /api/profiles/1/observations': () => json({ detail: 'errors.generic' }, 500),
    })
    renderRoutes([{ path: '/records', element: <HealthSummary /> }], '/records')
    const fbs = await screen.findByRole('link', { name: /FBS/ })
    await new Promise(r => setTimeout(r, 50))
    expect(within(fbs).queryByText('Unang resulta')).toBeNull()
    expect(within(fbs).queryByText('Tumaas')).toBeNull()
    expect(fbs.textContent).toContain('132')
  })
})

describe('HealthSummary with mixed units', () => {
  test('the trend compares with the previous value in the same unit only', async () => {
    const series = [obs('fbs', 140, '2024-07-02'), obs('fbs', 7.3, '2025-06-03', { unit: 'mmol/L' }), obs('fbs', 132, '2026-07-07')]
    mockFetch({
      'GET /api/profiles/1/summary': () => json(summary({ fbs: series[2] })),
      'GET /api/profiles/1/observations': () => json(series),
    })
    renderRoutes([{ path: '/records', element: <HealthSummary /> }], '/records')
    const fbs = await screen.findByRole('link', { name: /FBS/ })
    // 140 mg/dL -> 132 mg/dL is down; comparing with 7.3 mmol/L would have said "up"
    expect(await within(fbs).findByText('Bumaba')).toBeTruthy()
  })
})
