import { cleanup, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest'
import { DocumentViewer } from './DocumentViewer'
import { json, mockFetch, obs, renderRoutes } from './testing'

const PROPOSED = [
  obs('fbs', 132, '2026-07-07', { id: 101, status: 'proposed', document_id: 7 }),
  obs('hba1c', 7.2, '2026-07-07', { id: 102, status: 'proposed', document_id: 7 }),
]
const DOC = { id: 7, title: 'FBS and HbA1c', kind: 'lab', date: '2026-07-07', facility: null, pages: 1, status: 'indexed',
  error: null, transcript_md: '# Lab', observations: [...PROPOSED, obs('ldl', 120, '2025-01-01', { id: 50, document_id: 7 })] }
const routes = [{ path: '/records/documents/:id', element: <DocumentViewer /> }]

function setup() {
  return mockFetch({
    'GET /api/documents/7': () => json(DOC),
    'POST /api/documents/7/observations/confirm': () => new Response(null, { status: 204 }),
  })
}
const confirmPosts = (calls: ReturnType<typeof setup>['calls']) => calls.filter(c => c.method === 'POST')

beforeEach(() => localStorage.clear())
afterEach(() => { cleanup(); vi.unstubAllGlobals() })

describe('ReviewExtraction', () => {
  test('lists only the proposed values as rows with label, value, unit and date', async () => {
    setup()
    renderRoutes(routes, '/records/documents/7')
    const section = await screen.findByRole('region', { name: 'Tingnan po kung tama ang nabasa' })
    const rows = within(section).getAllByRole('listitem')
    expect(rows).toHaveLength(2)
    expect(rows[0].textContent).toContain('Fasting blood sugar')
    expect(rows[0].textContent).toContain('132')
    expect(rows[0].textContent).toContain('mg/dL')
    expect(rows[0].textContent).toMatch(/2026/)
    expect(section.textContent).not.toContain('120')
  })

  test('"Tama ito" confirms all with the ids and no edits, then toasts', async () => {
    const { calls } = setup()
    renderRoutes(routes, '/records/documents/7')
    await userEvent.click(await screen.findByRole('button', { name: 'Tama ito' }))
    await waitFor(() => expect(confirmPosts(calls)).toHaveLength(1))
    expect(confirmPosts(calls)[0].body).toEqual({ ids: [101, 102], edits: {} })
    expect(await screen.findByText('Naitabi na po ang mga resulta.')).toBeTruthy()
  })

  test('a row can be edited and another removed before confirming', async () => {
    const { calls } = setup()
    renderRoutes(routes, '/records/documents/7')
    const section = await screen.findByRole('region', { name: 'Tingnan po kung tama ang nabasa' })
    const [first, second] = within(section).getAllByRole('listitem')

    await userEvent.click(within(first).getByRole('button', { name: /Baguhin/ }))
    const value = within(first).getByLabelText('Resulta')
    await userEvent.clear(value)
    await userEvent.type(value, '128')
    const date = within(first).getByLabelText('Petsa')
    await userEvent.clear(date)
    await userEvent.type(date, '2026-07-08')
    await userEvent.click(within(first).getByRole('button', { name: /Tapos/ }))
    expect(first.textContent).toContain('128')

    await userEvent.click(within(second).getByRole('button', { name: /Alisin/ }))
    expect(within(section).getAllByRole('listitem')).toHaveLength(1)

    await userEvent.click(screen.getByRole('button', { name: 'Tama ito' }))
    await waitFor(() => expect(confirmPosts(calls)).toHaveLength(1))
    expect(confirmPosts(calls)[0].body).toEqual({ ids: [101], edits: { 101: { value: 128, unit: 'mg/dL', date: '2026-07-08' } } })
  })

  test('a value that is not a number cannot be saved', async () => {
    const { calls } = setup()
    renderRoutes(routes, '/records/documents/7')
    const section = await screen.findByRole('region', { name: 'Tingnan po kung tama ang nabasa' })
    const [first] = within(section).getAllByRole('listitem')
    await userEvent.click(within(first).getByRole('button', { name: /Baguhin/ }))
    const value = within(first).getByLabelText('Resulta')
    await userEvent.clear(value)
    await userEvent.type(value, 'abc')
    expect(within(first).getByText('Numero po ang ilagay.')).toBeTruthy()
    expect((screen.getByRole('button', { name: 'Tama ito' }) as HTMLButtonElement).disabled).toBe(true)
    expect(confirmPosts(calls)).toHaveLength(0)
  })
})
