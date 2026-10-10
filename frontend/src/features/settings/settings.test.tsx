import { cleanup, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { createMemoryRouter, RouterProvider } from 'react-router'
import { afterEach, beforeAll, beforeEach, describe, expect, test, vi } from 'vitest'
import { Providers } from '../../App'
import { routes } from '../../routes'
import { PROFILE_KEY } from '../lock/useLock'
import { TEXT_SCALE_KEY } from './textScale'

const json = (body: unknown, status = 200) =>
  new Response(status === 204 ? null : JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } })

const PROFILE = {
  id: 1, nickname: 'Lola Remy', full_name: 'Remedios Santos Dela Cruz', birth_date: '1953-03-14', sex: 'F',
  blood_type: 'O+', address: 'Quezon City', phone: '09171234567', philhealth_no: '12-345678901-2', senior_id_no: 'QC-1',
  language: 'tl',
}
const SUMMARY = { profile: PROFILE, conditions: [], allergies: [], meds: [], latest: {},
  contacts: [{ id: 7, name: 'Ana Dela Cruz', relation: 'Anak', phone: '09170000000', is_emergency: 1, is_doctor: 0, specialty: null, clinic: null }] }
const OWNER_SETTINGS = {
  actor: 'Lola Remy', role: 'owner', has_biometric: false,
  representatives: [{ id: 3, name: 'Ana Dela Cruz', relation: 'Daughter' }],
  emergency_fields: ['photo', 'age', 'blood_type', 'allergies', 'conditions', 'meds', 'contacts', 'doctor', 'philhealth_last4'],
}

type Call = { method: string; path: string; body: unknown }
let calls: Call[] = []

function mockApi(overrides: Record<string, (body: unknown) => Response> = {}) {
  calls = []
  const handlers: Record<string, (body: unknown) => Response> = {
    'GET /api/profiles': () => json([{ id: 1, nickname: 'Lola Remy', full_name: PROFILE.full_name, photo_url: null, has_biometric: false }]),
    'GET /api/profiles/1/summary': () => json(SUMMARY),
    'GET /api/profiles/1': () => json(PROFILE),
    'PUT /api/profiles/1': body => json({ ...PROFILE, ...(body as object) }),
    'GET /api/profiles/1/settings': () => json(OWNER_SETTINGS),
    'DELETE /api/profiles/1/representatives/3': () => json(null, 204),
    'GET /api/profiles/1/family-history': () => json([{ id: 1, relation: 'Ina', condition: 'Diabetes' }]),
    'GET /api/access-log': () => json([{ actor: 'Ana Dela Cruz', action: 'unlock', target: null, at: '2026-10-10 08:00:00' }]),
    ...overrides,
  }
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const method = init?.method ?? 'GET'
    const path = String(input).split('?')[0]
    const body = typeof init?.body === 'string' ? JSON.parse(init.body) : undefined
    calls.push({ method, path, body })
    const h = handlers[`${method} ${path}`]
    return h ? h(body) : json({ detail: 'errors.notFound' }, 404)
  }))
}

function renderAt(path: string) {
  const router = createMemoryRouter(routes, { initialEntries: [path] })
  render(<Providers><RouterProvider router={router} /></Providers>)
  return router
}

// jsdom has no modal <dialog>: open/close it the way the browser would, so the Sheet is reachable by role.
beforeAll(() => {
  const proto = HTMLDialogElement.prototype as HTMLDialogElement & { showModal: () => void; close: () => void }
  if (!proto.showModal) proto.showModal = function (this: HTMLDialogElement) { this.setAttribute('open', '') }
  if (!proto.close) proto.close = function (this: HTMLDialogElement) { this.removeAttribute('open'); this.dispatchEvent(new Event('close')) }
})

beforeEach(() => {
  localStorage.clear()
  localStorage.setItem(PROFILE_KEY, '1')
  document.documentElement.style.removeProperty('--text-scale')
})
afterEach(() => { cleanup(); vi.unstubAllGlobals() })

describe('settings', () => {
  test('switching language re-renders in Tagalog without a reload and saves it to the profile', async () => {
    localStorage.setItem('kapiling.lang', 'en')
    mockApi()
    renderAt('/settings')
    expect(await screen.findByRole('heading', { name: 'Text size' })).toBeTruthy()
    await userEvent.click(screen.getByRole('button', { name: 'Tagalog' }))
    expect(await screen.findByRole('heading', { name: 'Laki ng sulat' })).toBeTruthy()
    expect(screen.queryByRole('heading', { name: 'Text size' })).toBeNull()
    expect(screen.getByRole('button', { name: 'Tagalog' }).getAttribute('aria-pressed')).toBe('true')
    await waitFor(() => expect(calls).toContainEqual({ method: 'PUT', path: '/api/profiles/1', body: { language: 'tl' } }))
    expect(localStorage.getItem('kapiling.lang')).toBe('tl')
    expect(await screen.findByText('Tagalog na po ang wika.')).toBeTruthy()
  })

  test('text size sets --text-scale on <html> and remembers it', async () => {
    mockApi()
    renderAt('/settings')
    await userEvent.click(await screen.findByRole('button', { name: /150%/ }))
    expect(document.documentElement.style.getPropertyValue('--text-scale')).toBe('1.5')
    expect(localStorage.getItem(TEXT_SCALE_KEY)).toBe('1.5')
    expect(screen.getByRole('button', { name: /150%/ }).getAttribute('aria-pressed')).toBe('true')
    await userEvent.click(screen.getByRole('button', { name: /100%/ }))
    expect(document.documentElement.style.getPropertyValue('--text-scale')).toBe('1')
  })

  test('the stored text size is applied when the app starts, on any page', async () => {
    localStorage.setItem(TEXT_SCALE_KEY, '1.25')
    mockApi()
    renderAt('/meds')
    await screen.findByRole('navigation', { name: 'Pangunahing menu' })
    expect(document.documentElement.style.getPropertyValue('--text-scale')).toBe('1.25')
  })

  test('removing a representative asks for confirmation and then toasts', async () => {
    mockApi()
    renderAt('/settings')
    const row = (await screen.findByText('Ana Dela Cruz')).closest('li')!
    await userEvent.click(within(row).getByRole('button', { name: /Alisin/ }))
    expect(calls.some(c => c.method === 'DELETE')).toBe(false) // nothing happens before the confirmation
    const dialog = screen.getByRole('dialog', { name: 'Alisin si Ana Dela Cruz?' })
    await userEvent.click(within(dialog).getByRole('button', { name: /Opo, alisin/ }))
    await waitFor(() => expect(calls).toContainEqual({ method: 'DELETE', path: '/api/profiles/1/representatives/3', body: undefined }))
    expect(await screen.findByText('Inalis na po si Ana Dela Cruz.')).toBeTruthy()
  })

  test('cancelling the confirmation removes nothing', async () => {
    mockApi()
    renderAt('/settings')
    const row = (await screen.findByText('Ana Dela Cruz')).closest('li')!
    await userEvent.click(within(row).getByRole('button', { name: /Alisin/ }))
    const dialog = screen.getByRole('dialog', { name: 'Alisin si Ana Dela Cruz?' })
    await userEvent.click(within(dialog).getByRole('button', { name: 'Huwag na' }))
    expect(calls.some(c => c.method === 'DELETE')).toBe(false)
  })

  test('adding a representative with a PIN already in use shows the 409 message', async () => {
    mockApi({ 'POST /api/profiles/1/representatives': () => json({ detail: 'settings.pinInUse' }, 409) })
    renderAt('/settings')
    await userEvent.click(await screen.findByRole('button', { name: /Magdagdag ng representative/ }))
    const dialog = screen.getByRole('dialog', { name: /Magdagdag ng representative/ })
    await userEvent.type(within(dialog).getByLabelText('Pangalan'), 'Jun')
    await userEvent.type(within(dialog).getByLabelText(/PIN/), '123456')
    await userEvent.click(within(dialog).getByRole('button', { name: /I-save/ }))
    expect(await within(dialog).findByRole('alert')).toBeTruthy()
    expect(within(dialog).getByRole('alert').textContent).toMatch(/nagamit na/i)
  })

  test('a representative does not see owner-only controls', async () => {
    mockApi({ 'GET /api/profiles/1/settings': () => json({ ...OWNER_SETTINGS, actor: 'Ana Dela Cruz', role: 'representative', representatives: [] }) })
    renderAt('/settings')
    expect(await screen.findAllByText('Ang may-ari lang po ang puwedeng magbago nito.')).not.toHaveLength(0)
    expect(screen.queryByRole('button', { name: /Magdagdag ng representative/ })).toBeNull()
    expect(screen.queryByRole('button', { name: /Palitan ang PIN/ })).toBeNull()
    expect(screen.queryByRole('button', { name: /Tingnan kung sino/ })).toBeNull()
  })

  test('emergency card toggles save the selection', async () => {
    mockApi({ 'PUT /api/profiles/1/emergency-fields': body => json(body) })
    renderAt('/settings')
    const toggle = await screen.findByRole('switch', { name: 'Blood type' })
    expect((toggle as HTMLInputElement).checked).toBe(true)
    await userEvent.click(toggle)
    await waitFor(() => {
      const put = calls.find(c => c.method === 'PUT' && c.path === '/api/profiles/1/emergency-fields')
      expect(put).toBeTruthy()
      expect((put!.body as { fields: string[] }).fields).not.toContain('blood_type')
    })
  })

  test('the access log lists who opened the records', async () => {
    mockApi()
    renderAt('/settings')
    await userEvent.click(await screen.findByRole('button', { name: /Tingnan kung sino/ }))
    const dialog = screen.getByRole('dialog', { name: 'Sino ang nagbukas ng record ko' })
    expect(await within(dialog).findByText('Ana Dela Cruz')).toBeTruthy()
    expect(within(dialog).getByText('Binuksan ang Kapiling')).toBeTruthy()
  })

  test('lock now locks and returns to the lock screen', async () => {
    mockApi({ 'POST /api/lock': () => json(null, 204) })
    const router = renderAt('/settings')
    await userEvent.click(await screen.findByRole('button', { name: /I-lock ngayon/ }))
    await waitFor(() => expect(router.state.location.pathname).toBe('/lock'))
    expect(localStorage.getItem(PROFILE_KEY)).toBeNull()
  })
})

describe('profile', () => {
  test('the personal information form has labels above 56px inputs with the right inputmode, and saves', async () => {
    mockApi()
    renderAt('/profile')
    const phone = await screen.findByLabelText('Telepono') as HTMLInputElement
    await waitFor(() => expect(phone.value).toBe('09171234567'))
    expect(phone.getAttribute('inputmode')).toBe('tel')
    expect((screen.getByLabelText('PhilHealth number') as HTMLInputElement).getAttribute('inputmode')).toBe('numeric')
    expect(phone.className).toContain('field__input')
    await userEvent.clear(phone)
    await userEvent.type(phone, '09998887777')
    await userEvent.click(screen.getByRole('button', { name: /I-save ang impormasyon/ }))
    await waitFor(() => expect(calls.find(c => c.method === 'PUT' && c.path === '/api/profiles/1')?.body).toMatchObject({ phone: '09998887777' }))
    expect(await screen.findByText('Na-save na po.')).toBeTruthy()
  })

  test('family history and contacts are listed', async () => {
    mockApi()
    renderAt('/profile')
    expect(await screen.findByText(/Diabetes/)).toBeTruthy()
    expect(await screen.findByText('Ana Dela Cruz')).toBeTruthy()
  })
})

test('the text-size effect is one line in the app root', async () => {
  const { readFileSync } = await import('node:fs')
  const app = readFileSync('src/App.tsx', 'utf8')
  expect(app.match(/useStoredTextScale\(\)/g)).toHaveLength(1)
})
