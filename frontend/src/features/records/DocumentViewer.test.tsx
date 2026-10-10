import { act, cleanup, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest'
import { DocumentViewer } from './DocumentViewer'
import { json, mockFetch, renderRoutes } from './testing'

const MD = '# Marikina Valley Diagnostic Center\n\n## Results\n\n| Test | Result | Unit |\n|---|---|---|\n| FBS | 132 | mg/dL |\n\nReleased 2026-07-07'
const DOC = { id: 7, title: 'FBS and HbA1c', kind: 'lab', date: '2026-07-07', facility: 'Marikina Valley Diagnostic Center',
  pages: 2, page_urls: ['/api/documents/7/page/1.png?v=a', '/api/documents/7/page/2.png?v=a'],
  status: 'indexed', error: null, transcript_md: MD, observations: [] }
const routes = [{ path: '/records/documents/:id', element: <DocumentViewer /> }]

beforeEach(() => {
  localStorage.clear()
  Element.prototype.scrollIntoView = vi.fn()
})
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.useRealTimers() })

describe('DocumentViewer', () => {
  test('shows each page image and reveals the transcribed text on request', async () => {
    mockFetch({ 'GET /api/documents/7': () => json(DOC) })
    renderRoutes(routes, '/records/documents/7')
    expect(await screen.findByRole('heading', { level: 1, name: 'FBS and HbA1c' })).toBeTruthy()
    const imgs = screen.getAllByRole('img') as HTMLImageElement[]
    expect(imgs.map(i => i.getAttribute('src'))).toEqual(DOC.page_urls)
    expect(screen.queryByText('Released 2026-07-07')).toBeNull()
    await userEvent.click(screen.getByRole('button', { name: 'Basahin ang nakasulat' }))
    expect(screen.getByText('Released 2026-07-07')).toBeTruthy()
  })

  test('the page image zooms in and out with labelled buttons', async () => {
    mockFetch({ 'GET /api/documents/7': () => json(DOC) })
    renderRoutes(routes, '/records/documents/7')
    await screen.findByRole('heading', { level: 1, name: 'FBS and HbA1c' })
    const zoomIn = screen.getByRole('button', { name: 'Palakihin' })
    const zoomOut = screen.getByRole('button', { name: 'Paliitin' })
    expect((zoomOut as HTMLButtonElement).disabled).toBe(true)
    await userEvent.click(zoomIn)
    expect((zoomOut as HTMLButtonElement).disabled).toBe(false)
    const img = screen.getAllByRole('img')[0] as HTMLImageElement
    expect(img.style.width).toBe('150%')
  })

  test('while reading it says so and polls every 3 s', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    let reads = 0
    mockFetch({ 'GET /api/documents/7': () => { reads++; return json({ ...DOC, status: reads < 3 ? 'queued' : 'reading', transcript_md: null }) } })
    renderRoutes(routes, '/records/documents/7')
    expect(await screen.findByText('Binabasa pa po ni Kapiling...')).toBeTruthy()
    expect(reads).toBe(1)
    await act(async () => { vi.advanceTimersByTime(3100) })
    await waitFor(() => expect(reads).toBe(2))
    await act(async () => { vi.advanceTimersByTime(3100) })
    await waitFor(() => expect(reads).toBe(3))
    expect(screen.queryByRole('button', { name: 'Basahin ang nakasulat' })).toBeNull()
  })

  test('a failed read says so plainly', async () => {
    mockFetch({ 'GET /api/documents/7': () => json({ ...DOC, status: 'failed', error: 'vision_unavailable', transcript_md: null }) })
    renderRoutes(routes, '/records/documents/7')
    expect(await screen.findByText('Hindi po nabasa ni Kapiling ang dokumentong ito.')).toBeTruthy()
  })

  test('from a citation it opens the text, scrolls to and highlights the verbatim match', async () => {
    mockFetch({ 'GET /api/documents/7': () => json(DOC) })
    renderRoutes(routes, { pathname: '/records/documents/7', search: '?chunk=12',
      state: { source: { chunk_id: 12, before: '| FBS | ', match: '132', after: ' | mg/dL |' } } })
    const mark = await screen.findByText('132', { selector: 'mark' })
    expect(mark).toBeTruthy()
    expect(screen.getByText('Released 2026-07-07')).toBeTruthy()
    await waitFor(() => expect(Element.prototype.scrollIntoView).toHaveBeenCalled())
  })

  test('a citation whose context is not verbatim opens at the top with no highlight', async () => {
    mockFetch({ 'GET /api/documents/7': () => json(DOC) })
    renderRoutes(routes, { pathname: '/records/documents/7', search: '?chunk=12',
      state: { source: { chunk_id: 12, before: '| HbA1c | ', match: '132', after: ' | mg/dL |' } } })
    await screen.findByRole('heading', { level: 1, name: 'FBS and HbA1c' })
    expect(document.querySelector('mark')).toBeNull()
    expect(Element.prototype.scrollIntoView).not.toHaveBeenCalled()
  })

  test('a missing document shows the error state with Retry', async () => {
    mockFetch({})
    renderRoutes(routes, '/records/documents/99')
    expect(await screen.findByRole('alert')).toBeTruthy()
    expect(screen.getByRole('heading', { level: 1 })).toBeTruthy()
  })
})
