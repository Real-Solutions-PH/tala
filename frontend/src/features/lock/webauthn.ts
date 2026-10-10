// Browser side of biometric unlock (WebAuthn, platform authenticator, user verification required).
// The server sends options as JSON with base64url byte fields; the browser API wants ArrayBuffers.
import { api } from '../../api/client'

export function b64urlEncode(buf: ArrayBuffer): string {
  let s = ''
  for (const b of new Uint8Array(buf)) s += String.fromCharCode(b)
  return btoa(s).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')
}

export function b64urlDecode(s: string): ArrayBuffer {
  const bin = atob(s.replace(/-/g, '+').replace(/_/g, '/') + '='.repeat((4 - (s.length % 4)) % 4))
  const out = new Uint8Array(bin.length)
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i)
  return out.buffer
}

/** True only when this device has Face ID / Touch ID / fingerprint that WebAuthn can use. Never throws. */
export async function biometricAvailable(): Promise<boolean> {
  try {
    const PKC = globalThis.PublicKeyCredential
    if (!PKC || typeof PKC.isUserVerifyingPlatformAuthenticatorAvailable !== 'function') return false
    return await PKC.isUserVerifyingPlatformAuthenticatorAvailable()
  } catch {
    return false
  }
}

type Descriptor = { id: string; type: 'public-key'; transports?: AuthenticatorTransport[] }
type CreationJSON = Omit<PublicKeyCredentialCreationOptions, 'challenge' | 'user' | 'excludeCredentials'> & {
  challenge: string; user: { id: string; name: string; displayName: string }; excludeCredentials?: Descriptor[]
}
type RequestJSON = Omit<PublicKeyCredentialRequestOptions, 'challenge' | 'allowCredentials'> & {
  challenge: string; allowCredentials?: Descriptor[]
}

const descriptor = (d: Descriptor): PublicKeyCredentialDescriptor => ({ ...d, id: b64urlDecode(d.id) })

function toJSON(cred: PublicKeyCredential): Record<string, unknown> {
  const r = cred.response as AuthenticatorResponse & Partial<AuthenticatorAttestationResponse & AuthenticatorAssertionResponse>
  const response: Record<string, string | null> = { clientDataJSON: b64urlEncode(r.clientDataJSON) }
  if (r.attestationObject) response.attestationObject = b64urlEncode(r.attestationObject)
  if (r.authenticatorData) response.authenticatorData = b64urlEncode(r.authenticatorData)
  if (r.signature) response.signature = b64urlEncode(r.signature)
  if (r.userHandle !== undefined) response.userHandle = r.userHandle ? b64urlEncode(r.userHandle) : null
  return {
    id: cred.id, rawId: b64urlEncode(cred.rawId), type: cred.type, response,
    authenticatorAttachment: cred.authenticatorAttachment ?? 'platform',
    clientExtensionResults: cred.getClientExtensionResults?.() ?? {},
  }
}

/** Owner, unlocked, re-entering the PIN: create a platform credential and store it on the server. */
export async function enrolBiometric(pin: string): Promise<void> {
  const o = await api.send<CreationJSON>('POST', '/webauthn/register/options', { pin })
  const cred = await navigator.credentials.create({
    publicKey: {
      ...o, challenge: b64urlDecode(o.challenge), user: { ...o.user, id: b64urlDecode(o.user.id) },
      excludeCredentials: o.excludeCredentials?.map(descriptor),
    },
  }) as PublicKeyCredential | null
  if (!cred) throw new Error('cancelled')
  await api.send('POST', '/webauthn/register/verify', { credential: toJSON(cred) })
}

/** Lock screen: prove the owner's biometric; on success the server sets the session cookie. */
export async function unlockWithBiometric(profileId: number): Promise<void> {
  const o = await api.send<RequestJSON>('POST', '/webauthn/login/options', { profile_id: profileId })
  const cred = await navigator.credentials.get({
    publicKey: { ...o, challenge: b64urlDecode(o.challenge), allowCredentials: o.allowCredentials?.map(descriptor) },
  }) as PublicKeyCredential | null
  if (!cred) throw new Error('cancelled')
  await api.send('POST', '/webauthn/login/verify', { profile_id: profileId, credential: toJSON(cred) })
}
