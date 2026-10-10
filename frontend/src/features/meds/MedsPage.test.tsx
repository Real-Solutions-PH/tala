import { cleanup, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { createMemoryRouter, RouterProvider } from 'react-router'
import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest'
import { Providers } from '../../App'
import { routes } from '../../routes'
import { PROFILE_KEY } from '../lock/useLock'

const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } })

const med = (id: number, name: string, strength: string, schedule: string[], supply_left: number, purpose: string) => ({
  id, name, strength, form: 'tablet', purpose, prescriber: 'Dr. Jose Reyes', schedule, start_date: '2024-01-10',
  end_date: null, supply_left, active: 1,
})
const DAY = {
  meds: [
    med(1, 'Losartan', '50 mg', ['08:00'], 24, 'Blood pressure'),
    med(2, 'Metformin', '500 mg', ['08:00', '20:00'], 40, 'Blood sugar'),
    med(3, 'Amlodipine', '5 mg', ['20:00'], 5, 'Blood pressure'),
  ],
  today: [
    { med_id: 1, name: 'Losartan', strength: '50 mg', slot: '08:00', taken_at: null },
    { med_id: 2, name: 'Metformin', strength: '500 mg', slot: '08:00', taken_at: '2026-10-10T08:05:00' },
    { med_id: 2, name: 'Metformin', strength: '500 mg', slot: '20:00', taken_at: null },
    { med_id: 3, name: 'Amlodipine', strength: '5 mg', slot: '20:00', taken_at: null },
  ],
}

type Handler = (init?: RequestInit) => Response | Promise<Response>
function mockApi(overrides: Record<string, Handler> = {}) {
  const handlers: Record<string, Handler> = {
    '/api/profiles': () => json([{ id: 1, nickname: 'Lola Remy', full_name: 'R', photo_url: null }]),
    '/api/profiles/1/summary': () => json({ profile: { id: 1 }, conditions: [], allergies: [], meds: [], latest: {}, contacts: [] }),
    '/api/profiles/1/meds': () => json(DAY),
    '/api/profiles/1/meds/1/taken': () => new Response(null, { status: 204 }),
    ...overrides,
  }
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const h = handlers[String(input).split('?')[0]]
    return h ? h(init) : json({ detail: 'errors.notFound' }, 404)
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

function renderAt(path: string) {
  const router = createMemoryRouter(routes, { initialEntries: [path] })
  render(<Providers><RouterProvider router={router} /></Providers>)
  return router
}

const losartanRow = async () => (await screen.findAllByTestId('dose')).find(r => r.textContent?.includes('Losartan'))!

beforeEach(() => { localStorage.clear(); localStorage.setItem(PROFILE_KEY, '1') })
afterEach(() => { cleanup(); vi.unstubAllGlobals() })

describe('MedsPage', () => {
  test('groups today by Umaga, Tanghali, Gabi : untaken doses offer "Markahang nainom", taken ones show "Nainom na"', async () => {
    mockApi()
    renderAt('/meds')
    expect(await screen.findByRole('heading', { name: 'Ngayong araw' })).toBeTruthy()
    const umaga = screen.getByRole('region', { name: 'Umaga' })
    expect(within(umaga).getAllByTestId('dose')).toHaveLength(2)
    const gabi = screen.getByRole('region', { name: 'Gabi' })
    expect(within(gabi).getAllByTestId('dose')).toHaveLength(2)
    expect(screen.queryByRole('region', { name: 'Tanghali' })).toBeNull()
    const metforminAm = within(umaga).getAllByTestId('dose').find(r => r.textContent?.includes('Metformin'))!
    expect(within(metforminAm).getByRole('button', { name: /^Nainom na/ }).getAttribute('aria-pressed')).toBe('true')
    const losartan = within(umaga).getAllByTestId('dose').find(r => r.textContent?.includes('Losartan'))!
    expect(within(losartan).getByRole('button', { name: /^Markahang nainom/ }).getAttribute('aria-pressed')).toBe('false')
    expect(within(losartan).queryByRole('button', { name: /^Nainom na/ })).toBeNull()
  })

  test('marking a med taken calls POST and shows the success toast', async () => {
    let answer!: (r: Response) => void
    const f = mockApi({ '/api/profiles/1/meds/1/taken': () => new Promise<Response>(r => { answer = r }) })
    renderAt('/meds')
    const btn = within(await losartanRow()).getByRole('button', { name: /^Markahang nainom/ })
    expect(btn.getAttribute('aria-pressed')).toBe('false')
    await userEvent.click(btn)
    await waitFor(() => expect(btn.getAttribute('aria-pressed')).toBe('true')) // optimistic: before the server answers
    expect(btn.textContent).toBe('Nainom na') // the action became the status
    expect(screen.queryByText('Nainom na po ang Losartan.')).toBeNull()
    answer(new Response(null, { status: 204 }))
    const post = f.mock.calls.find(c => String(c[0]) === '/api/profiles/1/meds/1/taken')!
    expect((post[1] as RequestInit).method).toBe('POST')
    expect(JSON.parse(String((post[1] as RequestInit).body))).toMatchObject({ slot: '08:00' })
    expect(JSON.parse(String((post[1] as RequestInit).body)).date).toMatch(/^\d{4}-\d{2}-\d{2}$/)
    expect(await screen.findByText('Nainom na po ang Losartan.')).toBeTruthy()
  })

  test('on failure the toggle reverts and the error toast shows', async () => {
    mockApi({ '/api/profiles/1/meds/1/taken': () => json({ detail: 'x' }, 500) })
    renderAt('/meds')
    const btn = within(await losartanRow()).getByRole('button', { name: /^Markahang nainom/ })
    await userEvent.click(btn)
    expect(await screen.findByText('Hindi po natuloy. Pakisubukan ulit.')).toBeTruthy()
    await waitFor(() => expect(btn.getAttribute('aria-pressed')).toBe('false'))
    expect(btn.textContent).toBe('Markahang nainom')
  })

  test('shows a refill badge when supply_left <= 7, and lists all medicines with purpose and prescriber', async () => {
    mockApi()
    renderAt('/meds')
    expect((await screen.findAllByText('Bumili na po: 5 na lang ang natitira')).length).toBeGreaterThan(0)
    const all = screen.getByRole('region', { name: 'Lahat ng gamot' })
    expect(within(all).getAllByText(/Blood pressure/).length).toBe(2)
    expect(within(all).getAllByText(/Dr\. Jose Reyes/).length).toBe(3)
  })

  test('accepts schedule as JSON text, which is how the backend sends it today', async () => {
    const asText = { ...DAY, meds: DAY.meds.map(m => ({ ...m, schedule: JSON.stringify(m.schedule) })) }
    mockApi({ '/api/profiles/1/meds': () => json(asText) })
    renderAt('/meds')
    const all = await screen.findByRole('region', { name: 'Lahat ng gamot' })
    expect(within(all).getAllByText(/^Oras: /)).toHaveLength(3)
  })

  test('shows a skeleton while pending, not the empty state', async () => {
    mockApi({ '/api/profiles/1/meds': () => new Promise(() => {}) })
    renderAt('/meds')
    expect(await screen.findByRole('heading', { level: 1 })).toBeTruthy()
    expect(document.querySelector('.skeleton')).toBeTruthy()
    expect(screen.queryByText('Wala pa pong gamot')).toBeNull()
  })

  test('empty and error states', async () => {
    mockApi({ '/api/profiles/1/meds': () => json({ meds: [], today: [] }) })
    renderAt('/meds')
    expect(await screen.findByText('Wala pa pong gamot')).toBeTruthy()
    cleanup()
    mockApi({ '/api/profiles/1/meds': () => json({ detail: 'errors.notFound' }, 404) })
    renderAt('/meds')
    const alert = await screen.findByRole('alert')
    expect(within(alert).getByRole('button', { name: /Subukan ulit/ })).toBeTruthy()
  })
})
