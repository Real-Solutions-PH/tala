import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { createMemoryRouter, RouterProvider } from 'react-router'
import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest'
import { Providers } from '../../App'
import { routes } from '../../routes'
import { PROFILE_KEY } from '../lock/useLock'

const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } })

const soon = new Date(Date.now() + 20 * 86_400_000).toISOString().slice(0, 10)
const CARDS = [
  { id: 3, kind: 'philhealth', label: 'PhilHealth', number_masked: '••••0000', front_url: '/api/files/3/front', back_url: '/api/files/3/back', expires: null },
  { id: 4, kind: 'hmo', label: 'HMO (CareFirst)', number_masked: '••••0000', front_url: '/api/files/4/front', back_url: null, expires: soon },
  { id: 5, kind: 'senior', label: 'Senior Citizen ID', number_masked: null, front_url: '/api/files/5/front', back_url: null, expires: '2099-01-01' },
]

type Handler = (init?: RequestInit) => Response | Promise<Response>
function mockApi(cards: Handler) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const path = String(input).split('?')[0]
    if (path === '/api/profiles') return json([{ id: 1, nickname: 'Lola Remy', full_name: 'R', photo_url: null }])
    if (path === '/api/profiles/1/summary') return json({ profile: { id: 1 }, conditions: [], allergies: [], meds: [], latest: {}, contacts: [] })
    if (path === '/api/profiles/1/cards') return cards(init)
    return json({ detail: 'errors.notFound' }, 404)
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

function renderAt(path: string) {
  const router = createMemoryRouter(routes, { initialEntries: [path] })
  render(<Providers><RouterProvider router={router} /></Providers>)
  return router
}

beforeEach(() => {
  localStorage.clear(); localStorage.setItem(PROFILE_KEY, '1')
  // jsdom has no modal <dialog>: open and close it by attribute so the sheet's contents are accessible.
  HTMLDialogElement.prototype.showModal = function (this: HTMLDialogElement) { this.setAttribute('open', '') }
  HTMLDialogElement.prototype.close = function (this: HTMLDialogElement) { this.removeAttribute('open'); this.dispatchEvent(new Event('close')) }
})
afterEach(() => { cleanup(); vi.unstubAllGlobals() })

describe('CardsPage', () => {
  test('lists cards as thumbnails with labels, and an expiry badge only within 60 days', async () => {
    mockApi(() => json(CARDS))
    renderAt('/cards')
    expect(await screen.findByText('HMO (CareFirst)')).toBeTruthy()
    expect(screen.getByText('PhilHealth')).toBeTruthy()
    const imgs = document.querySelectorAll('img.wallet__thumb')
    expect(imgs).toHaveLength(3)
    expect(document.querySelectorAll('.wallet__item .badge')).toHaveLength(1)
  })

  test('tapping a card opens the full-screen viewer', async () => {
    mockApi(() => json(CARDS))
    const router = renderAt('/cards')
    await userEvent.click(await screen.findByRole('link', { name: /PhilHealth/ }))
    await waitFor(() => expect(router.state.location.pathname).toBe('/cards/3'))
    expect(await screen.findByRole('dialog')).toBeTruthy()
    await userEvent.click(screen.getByRole('button', { name: 'Isara' }))
    await waitFor(() => expect(router.state.location.pathname).toBe('/cards'))
    // Focus returns to the thumbnail that opened the viewer.
    await waitFor(() => expect(document.activeElement).toBe(screen.getByRole('link', { name: /PhilHealth/ })))
  })

  test('empty state says there are no cards yet and offers to add one', async () => {
    mockApi(() => json([]))
    renderAt('/cards')
    expect(await screen.findByRole('heading', { name: 'Wala pang card.' })).toBeTruthy()
    expect(screen.getByText('Kunan ng litrato ang PhilHealth card.')).toBeTruthy()
    await userEvent.click(screen.getByRole('button', { name: 'Magdagdag ng card' }))
    expect(await screen.findByLabelText(/Litrato ng harap/)).toBeTruthy()
  })

  test('adding a card posts multipart front and back', async () => {
    let posted: FormData | null = null
    const f = mockApi(init => {
      if (init?.method === 'POST') { posted = init.body as FormData; return json(CARDS[0]) }
      return json([])
    })
    renderAt('/cards')
    await userEvent.click(await screen.findByRole('button', { name: 'Magdagdag ng card' }))
    const front = new File(['a'], 'front.jpg', { type: 'image/jpeg' })
    const back = new File(['b'], 'back.jpg', { type: 'image/jpeg' })
    await userEvent.upload(screen.getByLabelText(/Litrato ng harap/), front)
    await userEvent.upload(screen.getByLabelText(/Litrato ng likod/), back)
    await userEvent.click(screen.getByRole('button', { name: 'Itago ang card' }))
    await waitFor(() => expect(posted).not.toBeNull())
    const fd = posted as unknown as FormData
    expect(fd.get('kind')).toBe('philhealth')
    expect(fd.get('label')).toBe('PhilHealth')
    expect((fd.get('front') as File).name).toBe('front.jpg')
    expect((fd.get('back') as File).name).toBe('back.jpg')
    expect(f.mock.calls.some(c => String(c[0]) === '/api/profiles/1/cards' && (c[1] as RequestInit)?.method === 'POST')).toBe(true)
    expect(await screen.findByText('Naitago na po ang card.')).toBeTruthy()
  })

  test('an upload error shows the catalogue text for the server detail', async () => {
    mockApi(init => init?.method === 'POST' ? json({ detail: 'errors.fileTooLarge' }, 413) : json([]))
    renderAt('/cards')
    await userEvent.click(await screen.findByRole('button', { name: 'Magdagdag ng card' }))
    await userEvent.upload(screen.getByLabelText(/Litrato ng harap/), new File(['a'], 'f.jpg', { type: 'image/jpeg' }))
    await userEvent.click(screen.getByRole('button', { name: 'Itago ang card' }))
    expect((await screen.findAllByText(/Masyadong malaki ang litrato/)).length).toBeGreaterThan(0)
  })

  test('shows a skeleton while pending, not the empty state', async () => {
    mockApi(() => new Promise(() => {}))
    renderAt('/cards')
    expect(await screen.findByRole('heading', { level: 1 })).toBeTruthy()
    expect(document.querySelector('.skeleton')).toBeTruthy()
    expect(screen.queryByText('Wala pang card.')).toBeNull()
  })
})
