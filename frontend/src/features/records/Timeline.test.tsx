import { cleanup, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest'
import { DocumentViewer } from './DocumentViewer'
import { RecordsPage } from './RecordsPage'
import { json, mockFetch, renderRoutes } from './testing'

const SUMMARY = { profile: { id: 1 }, conditions: [], allergies: [], meds: [], latest: {}, contacts: [] }
const TIMELINE = [
  { kind: 'lab', date: '2026-07-07', title: 'FBS and HbA1c', ref_id: 7 },
  { kind: 'visit', date: '2026-07-07', title: 'Maintenance check-up', ref_id: 3 },
  { kind: 'vaccine', date: '2025-04-10', title: 'Influenza Annual', ref_id: 1 },
]
const routes = [
  { path: '/records', element: <RecordsPage /> },
  { path: '/records/documents/:id', element: <DocumentViewer /> },
]

beforeEach(() => localStorage.clear())
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.useRealTimers() })

describe('Timeline', () => {
  test('filter chips refetch the timeline by kind and mark the selected one', async () => {
    const { calls } = mockFetch({
      'GET /api/profiles/1/summary': () => json(SUMMARY),
      'GET /api/profiles/1/timeline': ({ url }) => json(url.includes('kind=vaccine') ? [TIMELINE[2]] : TIMELINE),
    })
    renderRoutes(routes, '/records')
    const group = await screen.findByRole('group', { name: /Ipakita/ })
    expect(within(group).getAllByRole('button').map(b => b.textContent)).toEqual(['Lahat', 'Laboratoryo', 'Bakuna', 'Pagpapatingin', 'Dokumento'])
    expect(within(group).getByRole('button', { name: 'Lahat' }).getAttribute('aria-pressed')).toBe('true')
    await userEvent.click(within(group).getByRole('button', { name: 'Bakuna' }))
    expect(within(group).getByRole('button', { name: 'Bakuna' }).getAttribute('aria-pressed')).toBe('true')
    await waitFor(() => expect(calls.some(c => c.url.endsWith('/timeline?kind=vaccine'))).toBe(true))
    await waitFor(() => expect(screen.queryByText('Maintenance check-up')).toBeNull())
    expect(screen.getByText('Influenza Annual')).toBeTruthy()
  })

})
