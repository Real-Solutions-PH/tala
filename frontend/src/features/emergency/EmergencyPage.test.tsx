import { cleanup, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { createMemoryRouter, RouterProvider } from 'react-router'
import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest'
import { Providers } from '../../App'
import { routes } from '../../routes'

const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } })

const CARD = {
  profile_id: 1, name: 'Lola Remy', photo_url: '/api/profiles/1/photo', age: 73, blood_type: 'O+',
  allergies: [{ substance: 'Penicillin', reaction: 'Rash', severity: 'moderate' }, { substance: 'Shrimp', reaction: 'Hives', severity: 'mild' }],
  conditions: ['Hypertension', 'Type 2 diabetes'],
  meds: [{ name: 'Losartan', strength: '50 mg', schedule: ['08:00'] }],
  contacts: [{ name: 'Ana Dela Cruz', relation: 'Daughter', phone: '0917-000-0002' }],
  doctor: { name: 'Dr. Jose Reyes', clinic: 'Marikina Valley Medical Clinic', phone: '02-8000-0000' },
  philhealth_last4: '0000',
  qr_text: 'Lola Remy, 73',
}

function mockApi(emergency: () => Response | Promise<Response>) {
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
    const path = String(input).split('?')[0]
    if (path === '/api/emergency/1') return emergency()
    if (path === '/api/profiles') return json([])
    return json({ detail: 'errors.notFound' }, 404)
  }))
}

function renderAt(path: string) {
  const router = createMemoryRouter(routes, { initialEntries: [path] })
  render(<Providers><RouterProvider router={router} /></Providers>)
  return router
}

beforeEach(() => { localStorage.clear() })
afterEach(() => { cleanup(); vi.unstubAllGlobals() })

describe('EmergencyPage', () => {
  test('renders each allergy with an icon and the word "Allergy", not only red', async () => {
    mockApi(() => json(CARD))
    renderAt('/emergency/1')
    const badges = await screen.findAllByTestId('allergy')
    expect(badges).toHaveLength(2)
    for (const b of badges) {
      expect(b.textContent).toMatch(/Allergy/)
      expect(b.querySelector('svg')).toBeTruthy()
    }
    expect(badges[0].textContent).toContain('Penicillin')
  })

  test('contacts are tel: buttons named "Tawagan si Ana", and the band carries name and age', async () => {
    mockApi(() => json(CARD))
    renderAt('/emergency/1')
    const call = await screen.findByRole('link', { name: 'Tawagan si Ana' })
    expect(call.getAttribute('href')).toBe('tel:0917-000-0002')
    const band = document.querySelector('.ecard__band') as HTMLElement
    expect(within(band).getByText('Lola Remy')).toBeTruthy()
    expect(within(band).getByText('73 taong gulang')).toBeTruthy()
    expect(screen.getByText('O+')).toBeTruthy()
    expect(screen.getByText('•••• 0000')).toBeTruthy()
  })

  test('Back goes to the lock screen when nobody is unlocked', async () => {
    mockApi(() => json(CARD))
    renderAt('/emergency/1')
    expect((await screen.findByRole('link', { name: /Bumalik/ })).getAttribute('href')).toBe('/lock')
  })

  test('Show QR opens a sheet with the QR image', async () => {
    mockApi(() => json(CARD))
    renderAt('/emergency/1')
    await userEvent.click(await screen.findByRole('button', { name: /QR/ }))
    const img = document.querySelector('img.ecard__qr') as HTMLImageElement
    expect(img.getAttribute('src')).toBe('/api/emergency/1/qr.svg')
    expect(img.alt).toBeTruthy()
  })

  test('shows a skeleton while pending, not an empty card', async () => {
    mockApi(() => new Promise(() => {}))
    renderAt('/emergency/1')
    expect(await screen.findByRole('heading', { name: 'Emergency card' })).toBeTruthy()
    expect(document.querySelector('.skeleton')).toBeTruthy()
    expect(screen.queryByText('Walang kilalang allergy')).toBeNull()
  })

  test('an error says what happened and offers Retry', async () => {
    mockApi(() => json({ detail: 'Profile not found' }, 404))
    renderAt('/emergency/1')
    const alert = await screen.findByRole('alert')
    expect(within(alert).getByText('Hindi po namin ito mahanap.')).toBeTruthy()
    expect(within(alert).getByRole('button', { name: /Subukan ulit/ })).toBeTruthy()
  })
})
