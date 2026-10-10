import { cleanup, screen, waitFor } from '@testing-library/react'
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
  test('the filter dropdown refetches the timeline by kind and shows the chosen one', async () => {
    const { calls } = mockFetch({
      'GET /api/profiles/1/summary': () => json(SUMMARY),
      'GET /api/profiles/1/timeline': ({ url }) => json(url.includes('kind=vaccine') ? [TIMELINE[2]] : TIMELINE),
    })
    renderRoutes(routes, '/records')
    const select = await screen.findByRole('combobox', { name: /Ipakita/ }) as HTMLSelectElement
    expect([...select.options].map(o => o.textContent)).toEqual(['Lahat', 'Laboratoryo', 'Bakuna', 'Pagpapatingin', 'Dokumento'])
    expect(select.selectedOptions[0].textContent).toBe('Lahat')
    await userEvent.selectOptions(select, 'Bakuna')
    expect(select.selectedOptions[0].textContent).toBe('Bakuna')
    await waitFor(() => expect(calls.some(c => c.url.endsWith('/timeline?kind=vaccine'))).toBe(true))
    await waitFor(() => expect(screen.queryByText('Maintenance check-up')).toBeNull())
    expect(screen.getByText('Influenza Annual')).toBeTruthy()
  })

})
