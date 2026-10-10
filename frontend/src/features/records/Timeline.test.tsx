import { cleanup, screen } from '@testing-library/react'
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
  test('rows show the title and tags for type and date; lab and document rows open the document', async () => {
    mockFetch({
      'GET /api/profiles/1/summary': () => json(SUMMARY),
      'GET /api/profiles/1/timeline': () => json(TIMELINE),
    })
    renderRoutes(routes, '/records')
    expect(await screen.findByText('Maintenance check-up')).toBeTruthy()
    const lab = screen.getByRole('link', { name: /FBS and HbA1c/ })
    expect(lab.getAttribute('href')).toBe('/records/documents/7')
    expect(lab.querySelector('.tags2')?.textContent).toMatch(/Laboratoryo/)
    expect(screen.queryByRole('link', { name: /Influenza/ })).toBeNull()
    expect(screen.queryByRole('group', { name: /Ipakita/ })).toBeNull() // no filter chips, as in the prototype
  })
})
