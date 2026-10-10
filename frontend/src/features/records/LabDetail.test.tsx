import { cleanup, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest'
import { LabDetail, niceAxis } from './LabDetail'
import { json, mockFetch, obs, renderRoutes } from './testing'

const FBS = [
  obs('fbs', 118, '2024-07-02'), obs('fbs', 121, '2024-12-03'), obs('fbs', 125, '2025-06-03'),
  obs('fbs', 130, '2026-03-02'), obs('fbs', 132, '2026-07-07'),
]
const A1C = [obs('hba1c', 6.9, '2025-09-02'), obs('hba1c', 7.2, '2026-03-02')]

const MIXED = [
  obs('fbs', 118, '2024-07-02'), obs('fbs', 6.9, '2024-12-03', { unit: 'mmol/L', ref_low: 3.9, ref_high: 5.6 }), obs('fbs', 125, '2025-06-03'),
  obs('fbs', 128, '2025-12-02'), obs('fbs', 130, '2026-03-02'), obs('fbs', 132, '2026-07-07'),
]

function setup(code: string, lang: 'en' | 'tl' = 'tl', fbs = FBS) {
  mockFetch({ 'GET /api/profiles/1/observations': ({ url }) => json(url.includes('code=fbs') ? fbs : url.includes('code=hba1c') ? A1C : []) })
  return renderRoutes([{ path: '/records/labs/:code', element: <LabDetail /> }], `/records/labs/${code}`, lang)
}

beforeEach(() => localStorage.clear())
afterEach(() => { cleanup(); vi.unstubAllGlobals() })

describe('LabDetail', () => {
  test('a series of 4 or more draws a chart with an aria-label summary', async () => {
    setup('fbs', 'en')
    const chart = await screen.findByRole('img', { name: 'FBS rose from 118 to 132 mg/dL between July 2024 and July 2026' })
    expect(chart).toBeTruthy()
    expect(screen.getByRole('heading', { level: 1, name: 'FBS' })).toBeTruthy()
  })

  test('the table toggle shows the table alternative and back', async () => {
    setup('fbs')
    await screen.findByRole('img')
    expect(screen.queryByRole('table')).toBeNull()
    await userEvent.click(screen.getByRole('button', { name: 'Tingnan bilang talaan' }))
    const table = screen.getByRole('table')
    const rows = within(table).getAllByRole('row')
    expect(rows).toHaveLength(FBS.length + 1) // header + one per result
    expect(table.textContent).toContain('132')
    expect(table.textContent).toContain('mg/dL')
    expect(within(table).getAllByText('Mataas sa range').length).toBe(FBS.length)
    expect(screen.queryByRole('img')).toBeNull()
    await userEvent.click(screen.getByRole('button', { name: 'Tingnan bilang chart' }))
    expect(screen.getByRole('img')).toBeTruthy()
    expect(screen.queryByRole('table')).toBeNull()
  })

  test('fewer than 4 points shows stat cards instead of a chart', async () => {
    setup('hba1c')
    expect(await screen.findByText('7.2')).toBeTruthy()
    expect(screen.getByText('6.9')).toBeTruthy()
    expect(document.querySelectorAll('.stat-card')).toHaveLength(2)
    expect(screen.queryByRole('img')).toBeNull()
    expect(screen.queryByRole('button', { name: 'Tingnan bilang talaan' })).toBeNull()
    // the newest comes first, with its trend word
    const cards = [...document.querySelectorAll('.stat-card')]
    expect(cards[0].textContent).toContain('7.2')
    expect(within(cards[0] as HTMLElement).getByText('Tumaas')).toBeTruthy()
  })

  test('a series with another unit plots only the latest unit and says some were left out', async () => {
    setup('fbs', 'en', MIXED)
    expect(await screen.findByRole('img', { name: 'FBS rose from 118 to 132 mg/dL between July 2024 and July 2026' })).toBeTruthy()
    expect(screen.getByText('Some results are in a different unit and are not included.')).toBeTruthy()
    expect(screen.getByText('Normal range: 70–100 mg/dL')).toBeTruthy()
    await userEvent.click(screen.getByRole('button', { name: 'View as table' }))
    const table = screen.getByRole('table')
    expect(within(table).getAllByRole('row')).toHaveLength(MIXED.length) // header + the 5 mg/dL rows
    expect(table.textContent).not.toContain('mmol/L')
  })

  test('no notice when every result shares a unit', async () => {
    setup('fbs')
    await screen.findByRole('img')
    expect(screen.queryByText('Ilang resulta ay ibang unit at hindi isinama.')).toBeNull()
  })

  test('stat cards never show a trend across units', async () => {
    mockFetch({ 'GET /api/profiles/1/observations': () => json([obs('hba1c', 6.9, '2025-09-02', { unit: 'mmol/mol' }), obs('hba1c', 7.2, '2026-03-02')]) })
    renderRoutes([{ path: '/records/labs/:code', element: <LabDetail /> }], '/records/labs/hba1c')
    expect(await screen.findByText('Ilang resulta ay ibang unit at hindi isinama.')).toBeTruthy()
    expect(document.querySelectorAll('.stat-card')).toHaveLength(1)
    expect(screen.queryByText('Tumaas')).toBeNull()
  })

  test('no results shows an empty state', async () => {
    setup('ldl')
    expect(await screen.findByText('Wala pang resulta nito')).toBeTruthy()
  })
})

describe('niceAxis', () => {
  test('round ends and even steps', () => {
    expect(niceAxis(70, 132)).toEqual({ domain: [60, 140], ticks: [60, 80, 100, 120, 140] })
    const a = niceAxis(4, 7.2)
    expect(a.ticks[0]).toBeLessThanOrEqual(4)
    expect(a.ticks[a.ticks.length - 1]).toBeGreaterThanOrEqual(7.2)
  })
})
