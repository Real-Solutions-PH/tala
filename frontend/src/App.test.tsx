import { readFileSync } from 'node:fs'
import { act, cleanup, render, screen, waitFor, within } from '@testing-library/react'
import { createMemoryRouter, RouterProvider } from 'react-router'
import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest'
import { Providers } from './App'
import { routes } from './routes'
import { PROFILE_KEY } from './features/lock/useLock'

type Handler = (url: string) => Response
const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } })

const PROFILES = [{ id: 1, nickname: 'Lola Remy', full_name: 'Remedios Santos Dela Cruz', photo_url: null }]
const SUMMARY = { profile: { id: 1, nickname: 'Lola Remy', full_name: 'Remedios Santos Dela Cruz' }, conditions: [], allergies: [], meds: [], latest: {}, contacts: [] }
const EMERGENCY = { profile_id: 1, name: 'Remedios Santos Dela Cruz', photo_url: null, age: 73, blood_type: 'O+', allergies: [], conditions: [], meds: [], contacts: [], doctor: null, philhealth_last4: null, qr_text: 'x' }

function mockApi(overrides: Record<string, Handler> = {}) {
  const handlers: Record<string, Handler> = {
    '/api/profiles': () => json(PROFILES),
    '/api/profiles/1/summary': () => json(SUMMARY),
    '/api/emergency/1': () => json(EMERGENCY),
    ...overrides,
  }
  const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input)
    const path = url.split('?')[0]
    const h = handlers[path]
    return h ? h(url) : json({ detail: 'errors.notFound' }, 404)
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

function renderAt(path: string) {
  const router = createMemoryRouter(routes, { initialEntries: [path] })
  render(<Providers><RouterProvider router={router} /></Providers>)
  return router
}

beforeEach(() => { localStorage.clear() })
afterEach(() => { cleanup(); vi.unstubAllGlobals(); document.documentElement.style.removeProperty('--nav-h') })

describe('routing and the lock', () => {
  test('an unauthenticated visit to /chat lands on /lock', async () => {
    mockApi()
    const router = renderAt('/chat')
    await waitFor(() => expect(router.state.location.pathname).toBe('/lock'))
    expect(await screen.findByRole('heading', { name: 'Naka-lock ang Kapiling' })).toBeTruthy()
    expect(screen.queryByRole('navigation')).toBeNull()
  })

  test('/emergency/1 renders without a session', async () => {
    mockApi()
    const router = renderAt('/emergency/1')
    expect(await screen.findByRole('heading', { name: 'Emergency card' })).toBeTruthy()
    expect(await screen.findByText('Remedios Santos Dela Cruz')).toBeTruthy()
    expect(router.state.location.pathname).toBe('/emergency/1')
  })

  test('a 401 from the API clears the session and redirects to /lock', async () => {
    localStorage.setItem(PROFILE_KEY, '1')
    mockApi({ '/api/profiles/1/summary': () => json({ detail: 'errors.locked' }, 401) })
    const router = renderAt('/meds')
    await waitFor(() => expect(router.state.location.pathname).toBe('/lock'))
    expect(localStorage.getItem(PROFILE_KEY)).toBeNull()
  })

  test('a 403 shows the error state instead of redirecting', async () => {
    localStorage.setItem(PROFILE_KEY, '1')
    mockApi({ '/api/profiles/1/summary': () => json({ detail: 'errors.notYourProfile' }, 403) })
    const router = renderAt('/meds')
    const alert = await screen.findByRole('alert')
    expect(within(alert).getByRole('button', { name: /Subukan ulit/ })).toBeTruthy()
    expect(router.state.location.pathname).toBe('/meds')
  })

  test.each(['/home', '/chat', '/chat/abc', '/cards', '/cards/3', '/meds', '/records', '/records/labs/fbs', '/records/documents/2', '/settings', '/profile'])(
    'locked route %s renders inside the shell', async path => {
      localStorage.setItem(PROFILE_KEY, '1')
      mockApi()
      const router = renderAt(path)
      expect(await screen.findByRole('navigation', { name: 'Pangunahing menu' })).toBeTruthy()
      expect(screen.getByRole('heading', { level: 1 })).toBeTruthy()
      expect(router.state.location.pathname).toBe(path)
    })
})

describe('shell', () => {
  beforeEach(() => { localStorage.setItem(PROFILE_KEY, '1'); mockApi() })

  test('the dock has 4 tabs and the Kausap button, all with visible text, and marks the current one', async () => {
    renderAt('/meds')
    const nav = await screen.findByRole('navigation', { name: 'Pangunahing menu' })
    const links = within(nav).getAllByRole('link')
    expect(links.map(a => a.textContent)).toEqual(['Tahanan', 'Talaan', 'Card', 'Gamot', 'Kausap'])
    const current = links.filter(a => a.getAttribute('aria-current') === 'page')
    expect(current).toHaveLength(1)
    expect(current[0].textContent).toBe('Gamot')
  })

  test('a nested route keeps its tab current', async () => {
    renderAt('/records/labs/fbs')
    const nav = await screen.findByRole('navigation', { name: 'Pangunahing menu' })
    expect(within(nav).getByRole('link', { name: 'Talaan' }).getAttribute('aria-current')).toBe('page')
  })

  test('Home: the header greets the person and has Settings; Emergency is one tap away', async () => {
    renderAt('/home')
    const header = await screen.findByRole('banner')
    expect(await within(header).findByText('Lola Remy')).toBeTruthy()
    expect(within(header).getByRole('link', { name: /Settings/ })).toBeTruthy()
    const sos = await screen.findByRole('link', { name: /Emergency/ })
    expect(sos.getAttribute('href')).toBe('/emergency/1')
    expect(sos.querySelector('svg')).toBeTruthy()
  })

  test('other screens: a title bar with back, the screen name and the avatar', async () => {
    renderAt('/meds')
    const header = await screen.findByRole('banner')
    expect(within(header).getByRole('link', { name: 'Bumalik' }).getAttribute('href')).toBe('/home')
    expect(within(header).getByText('Gamot')).toBeTruthy()
    expect(within(header).getByRole('button', { name: /Palitan ang tao/ })).toBeTruthy()
  })

  test('one plane: header, main and nav are the only rows of the shell, main is the only scroller', async () => {
    renderAt('/chat')
    await screen.findByRole('navigation', { name: 'Pangunahing menu' })
    const shell = document.querySelector('.shell')!
    expect([...shell.children].map(c => c.tagName)).toEqual(['HEADER', 'MAIN', 'NAV'])
    const css = readFileSync('src/design/base.css', 'utf8')
    const rule = (sel: string) => css.match(new RegExp(`(?:^|\\n)${sel.replace('.', '\\.')}\\s*\\{([^}]*)\\}`))?.[1] ?? ''
    expect(rule('.shell')).toMatch(/grid-template-rows:\s*auto 1fr auto/)
    expect(rule('.shell')).toMatch(/height:\s*100dvh/)
    expect(rule('.shell__main')).toMatch(/overflow-y:\s*auto/)
    for (const sel of ['.shell', '.topbar', '.shell__main', '.bottomnav']) expect(rule(sel), sel).not.toMatch(/position:\s*(sticky|fixed)/)
    expect(rule('.topbar')).toMatch(/safe-area-inset-top/)
    expect(rule('.bottomnav')).toMatch(/safe-area-inset-bottom/)
  })

  test('toasts sit above the measured bottom nav', async () => {
    let cb: ResizeObserverCallback | undefined
    vi.stubGlobal('ResizeObserver', class {
      constructor(fn: ResizeObserverCallback) { cb = fn }
      observe() {} unobserve() {} disconnect() {}
    })
    renderAt('/chat')
    const nav = await screen.findByRole('navigation', { name: 'Pangunahing menu' })
    act(() => cb!([{ target: nav, borderBoxSize: [{ blockSize: 97, inlineSize: 375 }] } as unknown as ResizeObserverEntry], {} as ResizeObserver))
    expect(document.documentElement.style.getPropertyValue('--nav-h')).toBe('97px')
    const css = readFileSync('src/design/base.css', 'utf8')
    expect(css.match(/\n\.toasts\s*\{([^}]*)\}/)?.[1]).toMatch(/bottom:\s*calc\(var\(--nav-h/)
  })
})
