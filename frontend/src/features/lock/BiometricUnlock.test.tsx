import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import { Providers } from '../../App'
import { BiometricUnlock } from './BiometricUnlock'
import { PROFILE_KEY } from './useLock'
import { b64urlDecode, b64urlEncode } from './webauthn'

const json = (body: unknown, status = 200) =>
  new Response(status === 204 ? null : JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } })

const LOGIN_OPTIONS = { challenge: 'Y2hhbGxlbmdl', rpId: 'localhost', timeout: 120000, userVerification: 'required',
  allowCredentials: [{ id: 'Y3JlZC0x', type: 'public-key' }] }

function setPlatform(available: boolean | 'missing') {
  if (available === 'missing') { vi.stubGlobal('PublicKeyCredential', undefined); return }
  vi.stubGlobal('PublicKeyCredential', { isUserVerifyingPlatformAuthenticatorAvailable: vi.fn(async () => available) })
}

const enc = (s: string) => new TextEncoder().encode(s).buffer

function fakeAssertion() {
  return {
    id: 'Y3JlZC0x', rawId: enc('cred-1'), type: 'public-key', authenticatorAttachment: 'platform',
    response: { clientDataJSON: enc('{"challenge":"Y2hhbGxlbmdl"}'), authenticatorData: enc('auth'), signature: enc('sig'), userHandle: null },
    getClientExtensionResults: () => ({}),
  }
}

let fetchMock: ReturnType<typeof vi.fn>
let get: ReturnType<typeof vi.fn>

beforeEach(() => {
  localStorage.clear()
  fetchMock = vi.fn(async (input: RequestInfo | URL, _init?: RequestInit) => {
    const path = String(input)
    if (path === '/api/webauthn/login/options') return json(LOGIN_OPTIONS)
    if (path === '/api/webauthn/login/verify') return json(null, 204)
    return json([])
  })
  vi.stubGlobal('fetch', fetchMock)
  get = vi.fn(async () => fakeAssertion())
  Object.defineProperty(navigator, 'credentials', { value: { get, create: vi.fn() }, configurable: true })
})
afterEach(() => { cleanup(); vi.unstubAllGlobals() })

const mount = (props: Partial<{ hasBiometric: boolean; onUnlocked: () => void }> = {}) =>
  render(<Providers><BiometricUnlock profileId={1} hasBiometric={props.hasBiometric ?? true} onUnlocked={props.onUnlocked ?? (() => {})} /></Providers>)

const BUTTON = 'Buksan gamit ang Face ID / fingerprint'

test('shows the button only when a platform authenticator exists and the profile has a biometric', async () => {
  setPlatform(true)
  mount()
  expect(await screen.findByRole('button', { name: BUTTON })).toBeTruthy()
})

test('renders nothing without a platform authenticator', async () => {
  setPlatform(false)
  const { container } = mount()
  await waitFor(() => expect((globalThis.PublicKeyCredential as unknown as { isUserVerifyingPlatformAuthenticatorAvailable: ReturnType<typeof vi.fn> }).isUserVerifyingPlatformAuthenticatorAvailable).toHaveBeenCalled())
  expect(container.querySelector('button')).toBeNull()
})

test('renders nothing when the browser has no WebAuthn at all', async () => {
  setPlatform('missing')
  const { container } = mount()
  await new Promise(r => setTimeout(r, 0))
  expect(container.querySelector('button')).toBeNull()
})

test('renders nothing when the profile has no biometric enrolled', async () => {
  setPlatform(true)
  const { container } = mount({ hasBiometric: false })
  await new Promise(r => setTimeout(r, 0))
  expect(container.querySelector('button')).toBeNull()
})

test('a successful ceremony unlocks the profile and calls onUnlocked', async () => {
  setPlatform(true)
  const onUnlocked = vi.fn()
  mount({ onUnlocked })
  await userEvent.click(await screen.findByRole('button', { name: BUTTON }))
  await waitFor(() => expect(onUnlocked).toHaveBeenCalledOnce())
  const opts = get.mock.calls[0][0].publicKey
  expect(new TextDecoder().decode(opts.challenge)).toBe('challenge')
  expect(opts.userVerification).toBe('required')
  const verify = fetchMock.mock.calls.find(c => String(c[0]) === '/api/webauthn/login/verify')!
  const body = JSON.parse(verify[1].body)
  expect(body.profile_id).toBe(1)
  expect(body.credential.response.signature).toBe(b64urlEncode(enc('sig')))
  expect(body.credential.authenticatorAttachment).toBe('platform')
  expect(localStorage.getItem(PROFILE_KEY)).toBe('1')
})

test('a refused verify shows a message and stays locked', async () => {
  setPlatform(true)
  fetchMock.mockImplementation(async (input: RequestInfo | URL) =>
    String(input).endsWith('/options') ? json(LOGIN_OPTIONS) : json({ detail: 'settings.biometricFailed' }, 400))
  const onUnlocked = vi.fn()
  mount({ onUnlocked })
  await userEvent.click(await screen.findByRole('button', { name: BUTTON }))
  expect((await screen.findByRole('alert')).textContent).toMatch(/PIN/)
  expect(onUnlocked).not.toHaveBeenCalled()
  expect(localStorage.getItem(PROFILE_KEY)).toBeNull()
})

test('base64url round-trips', () => {
  const bytes = new Uint8Array([0, 250, 251, 252, 253, 254, 255])
  expect([...new Uint8Array(b64urlDecode(b64urlEncode(bytes.buffer)))]).toEqual([...bytes])
  expect(b64urlEncode(bytes.buffer)).not.toMatch(/[+/=]/)
})
