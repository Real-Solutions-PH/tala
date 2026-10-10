import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { createMemoryRouter, RouterProvider } from 'react-router'
import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest'
import { Providers } from '../../App'
import { routes } from '../../routes'

const json = (body: unknown, status = 200, headers: Record<string, string> = {}) =>
  new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json', ...headers } })

const PROFILES = [
  { id: 1, nickname: 'Lola Remy', full_name: 'Remedios Santos Dela Cruz', photo_url: null },
  { id: 2, nickname: 'Mika', full_name: 'Mika Dela Cruz', photo_url: null },
]

type Handler = (init?: RequestInit) => Response | Promise<Response>

function mockApi(overrides: Record<string, Handler> = {}) {
  const handlers: Record<string, Handler> = {
    '/api/profiles': () => json(PROFILES),
    '/api/unlock': () => new Response(null, { status: 204 }),
    '/api/profiles/1/summary': () => json({ profile: { id: 1 }, conditions: [], allergies: [], meds: [], latest: {}, contacts: [] }),
    '/api/profiles/2/summary': () => json({ profile: { id: 2 }, conditions: [], allergies: [], meds: [], latest: {}, contacts: [] }),
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

const unlockCalls = (f: ReturnType<typeof mockApi>) => f.mock.calls.filter(c => String(c[0]) === '/api/unlock')

async function typePin(digits: string) {
  for (const d of digits) await userEvent.click(screen.getByRole('button', { name: d }))
}

beforeEach(() => { localStorage.clear() })
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.useRealTimers() })

describe('LockScreen', () => {
  test('submits after the 6th digit and posts {profile_id, pin}', async () => {
    const f = mockApi()
    const router = renderAt('/lock?profile=2')
    await screen.findByRole('radio', { name: /Mika/ })
    expect(screen.getByRole('radio', { name: /Mika/ }).getAttribute('aria-checked')).toBe('true')
    await typePin('12345')
    expect(unlockCalls(f)).toHaveLength(0)
    await typePin('6')
    await waitFor(() => expect(unlockCalls(f)).toHaveLength(1))
    const init = unlockCalls(f)[0][1] as RequestInit
    expect(init.method).toBe('POST')
    expect(JSON.parse(String(init.body))).toEqual({ profile_id: 2, pin: '123456' })
    await waitFor(() => expect(router.state.location.pathname).toBe('/chat'))
  })

  test('PIN keys are labelled buttons, each digit shows a dot, and there is no biometric button', async () => {
    mockApi()
    renderAt('/lock')
    await screen.findByRole('radio', { name: /Lola Remy/ })
    for (const d of '0123456789') expect(screen.getByRole('button', { name: d })).toBeTruthy()
    expect(screen.queryByRole('button', { name: /fingerprint|mukha/i })).toBeNull()
    await typePin('12')
    expect(document.querySelectorAll('.pin-dot--on')).toHaveLength(2)
    await userEvent.click(screen.getByRole('button', { name: 'Burahin ang huling numero' }))
    expect(document.querySelectorAll('.pin-dot--on')).toHaveLength(1)
  })

  test('the red Emergency button opens the selected profile card without unlocking', async () => {
    mockApi()
    renderAt('/lock?profile=2')
    await screen.findByRole('radio', { name: /Mika/ })
    const sos = screen.getByRole('link', { name: /Emergency/ })
    expect(sos.getAttribute('href')).toBe('/emergency/2')
  })

  test('with no profile to select, Emergency is a disabled button, not a link', async () => {
    mockApi({ '/api/profiles': () => json([]) })
    renderAt('/lock')
    const sos = await screen.findByRole('button', { name: /Emergency/ })
    expect((sos as HTMLButtonElement).disabled).toBe(true)
    expect(screen.queryByRole('link', { name: /Emergency/ })).toBeNull()
  })

  test('a wrong PIN shows the error, shakes the dots and clears the PIN', async () => {
    mockApi({ '/api/unlock': () => json({ detail: 'errors.wrongPin' }, 401) })
    const router = renderAt('/lock?profile=1')
    await screen.findByRole('radio', { name: /Lola Remy/ })
    await typePin('111111')
    expect(await screen.findByText('Mali po ang PIN. Pakisubukan ulit.')).toBeTruthy()
    expect(document.querySelector('.pin-dots--shake')).toBeTruthy()
    expect(document.querySelectorAll('.pin-dot--on')).toHaveLength(0)
    expect(router.state.location.pathname).toBe('/lock')
  })

  test('429 shows the lockout text and a countdown, and the keys wait', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true, toFake: ['setInterval', 'clearInterval', 'Date'] })
    mockApi({ '/api/unlock': () => json({ detail: 'errors.tooManyAttempts' }, 429, { 'retry-after': '60' }) })
    renderAt('/lock?profile=1')
    await screen.findByRole('radio', { name: /Lola Remy/ })
    for (const d of '999999') fireEvent.click(screen.getByRole('button', { name: d }))
    expect(await screen.findByText(/Masyado na pong maraming maling PIN/)).toBeTruthy()
    expect(screen.getByText(/(60|59) segundo/)).toBeTruthy()
    expect((screen.getByRole('button', { name: '1' }) as HTMLButtonElement).disabled).toBe(true)
    act(() => { vi.advanceTimersByTime(2000) })
    expect(screen.getByText(/5[78] segundo/)).toBeTruthy()
    act(() => { vi.advanceTimersByTime(60_000) })
    expect(screen.queryByText(/segundo/)).toBeNull()
    expect((screen.getByRole('button', { name: '1' }) as HTMLButtonElement).disabled).toBe(false)
  })

  test('shows a skeleton while profiles load, not an empty list', async () => {
    mockApi({ '/api/profiles': () => new Promise(() => {}) })
    renderAt('/lock')
    expect(await screen.findByRole('heading', { name: 'Naka-lock ang Kapiling' })).toBeTruthy()
    expect(document.querySelector('.skeleton')).toBeTruthy()
    expect(screen.queryByRole('radio')).toBeNull()
  })

  describe('biometric unlock', () => {
    const withBio = [{ ...PROFILES[0], has_biometric: true }, PROFILES[1]]
    const platform = (ok: boolean) => vi.stubGlobal('PublicKeyCredential',
      { isUserVerifyingPlatformAuthenticatorAvailable: vi.fn(async () => ok) })

    test('renders the button when the profile has one and the device supports it', async () => {
      mockApi({ '/api/profiles': () => json(withBio) })
      platform(true)
      renderAt('/lock?profile=1')
      expect(await screen.findByRole('button', { name: /Face ID|fingerprint/i })).toBeTruthy()
    })

    test('does not render it without enrollment or without platform support', async () => {
      mockApi({ '/api/profiles': () => json(PROFILES) })
      platform(true)
      renderAt('/lock?profile=1')
      await screen.findByRole('radio', { name: /Lola Remy/ })
      await act(async () => {})
      expect(screen.queryByRole('button', { name: /Face ID|fingerprint/i })).toBeNull()
      cleanup()
      mockApi({ '/api/profiles': () => json(withBio) })
      platform(false)
      renderAt('/lock?profile=1')
      await screen.findByRole('radio', { name: /Lola Remy/ })
      await act(async () => {})
      expect(screen.queryByRole('button', { name: /Face ID|fingerprint/i })).toBeNull()
    })

    test('the biometric button is disabled during a 429 lockout', async () => {
      vi.useFakeTimers({ shouldAdvanceTime: true, toFake: ['setInterval', 'clearInterval', 'Date'] })
      mockApi({ '/api/profiles': () => json(withBio), '/api/unlock': () => json({ detail: 'errors.tooManyAttempts' }, 429, { 'retry-after': '60' }) })
      platform(true)
      renderAt('/lock?profile=1')
      const bio = await screen.findByRole('button', { name: /Face ID|fingerprint/i }) as HTMLButtonElement
      expect(bio.disabled).toBe(false)
      for (const d of '999999') fireEvent.click(screen.getByRole('button', { name: d }))
      await screen.findByText(/Masyado na pong maraming maling PIN/)
      expect((screen.getByRole('button', { name: /Face ID|fingerprint/i }) as HTMLButtonElement).disabled).toBe(true)
    })
  })
})
