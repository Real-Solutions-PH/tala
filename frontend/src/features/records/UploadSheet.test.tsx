import { act, cleanup, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest'
import { DocumentViewer } from './DocumentViewer'
import { RecordsPage } from './RecordsPage'
import { json, mockFetch, renderRoutes } from './testing'

const SUMMARY = { profile: { id: 1 }, conditions: [], allergies: [], meds: [], latest: {}, contacts: [] }
const routes = [
  { path: '/records', element: <RecordsPage /> },
  { path: '/records/documents/:id', element: <DocumentViewer /> },
]

beforeEach(() => localStorage.clear())
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.useRealTimers() })

describe('UploadSheet', () => {
  test('upload posts multipart, then the document page polls every 3 s until it is read', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    let reads = 0
    const { calls } = mockFetch({
      'GET /api/profiles/1/summary': () => json(SUMMARY),
      'GET /api/profiles/1/timeline': () => json([]),
      'POST /api/profiles/1/documents': () => json({ id: 7, status: 'queued' }, 201),
      'GET /api/documents/7': () => {
        reads++
        return json({ id: 7, title: 'Lab result', kind: 'lab', date: null, facility: null, pages: 1, error: null,
          status: reads < 2 ? 'reading' : 'indexed', transcript_md: reads < 2 ? null : '# Lab\n\nFBS 132 mg/dL', observations: [] })
      },
    })
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime })
    const { router } = renderRoutes(routes, '/records')
    await user.click(screen.getByRole('button', { name: 'Magdagdag ng resulta' }))

    const camera = document.querySelector<HTMLInputElement>('input[capture="environment"]')!
    expect(camera).toBeTruthy()
    expect(camera.accept).toContain('image/')
    const chooser = screen.getByLabelText('Pumili ng litrato o PDF') as HTMLInputElement
    expect(chooser.accept).toContain('application/pdf')

    const file = new File(['fake'], 'lab.jpg', { type: 'image/jpeg' })
    await user.upload(chooser, file)

    await waitFor(() => expect(calls.find(c => c.method === 'POST')).toBeTruthy())
    const post = calls.find(c => c.method === 'POST')!
    expect(post.path).toBe('/api/profiles/1/documents')
    expect(post.body).toBeInstanceOf(FormData)
    expect((post.body as FormData).get('file')).toBeInstanceOf(File)

    await waitFor(() => expect(router.state.location.pathname).toBe('/records/documents/7'))
    expect(await screen.findByText('Binabasa pa po ni Kapiling...')).toBeTruthy()
    expect(reads).toBe(1)
    await act(async () => { vi.advanceTimersByTime(3100) })
    await waitFor(() => expect(reads).toBe(2))
    expect(await screen.findByRole('button', { name: 'Basahin ang nakasulat' })).toBeTruthy()
    expect(screen.queryByText('Binabasa pa po ni Kapiling...')).toBeNull()
  })
})
