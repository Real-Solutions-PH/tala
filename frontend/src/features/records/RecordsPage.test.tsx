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

describe('RecordsPage', () => {
  test('has the title, the scan tile and the timeline', async () => {
    mockFetch({
      'GET /api/profiles/1/summary': () => json(SUMMARY),
      'GET /api/profiles/1/timeline': () => json(TIMELINE),
    })
    renderRoutes(routes, '/records')
    expect(screen.getByRole('heading', { level: 1, name: 'Rekord' })).toBeTruthy()
    const add = screen.getByRole('button', { name: 'Magdagdag ng resulta' })
    expect(add.className).toContain('scanbtn') // the prototype's dashed scan tile, 64 px or taller
    expect(await screen.findByText('Maintenance check-up')).toBeTruthy()
    // lab and document entries open the document; visits and vaccines are plain rows
    expect(screen.getByRole('link', { name: /FBS and HbA1c/ }).getAttribute('href')).toBe('/records/documents/7')
    expect(screen.queryByRole('link', { name: /Influenza/ })).toBeNull()
  })

})
