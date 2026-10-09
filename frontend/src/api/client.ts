// Thin fetch wrapper for the Kapiling API. Paths are relative to /api.
// A 401 from any locked route hands control to the unauthorized handler (the app sends the user to /lock).

export class ApiError extends Error {
  status: number
  /** The server's `detail`, usually an i18n key such as "errors.notYourProfile". */
  detail: string | null
  constructor(status: number, detail: string | null) {
    super(detail ?? `HTTP ${status}`)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
  }
}

type Handler = () => void
let onUnauthorized: Handler | null = null

/** Registered once by the router root. Pass null to clear it (tests). */
export function setOnUnauthorized(fn: Handler | null): void {
  onUnauthorized = fn
}

// A wrong PIN is a 401 too, but it must stay on the lock screen and show its own message.
const NO_REDIRECT = new Set(['/unlock'])

export const API_BASE = '/api'

async function errorFrom(res: Response): Promise<ApiError> {
  let detail: string | null = null
  try {
    const body = await res.json()
    if (body && typeof body.detail === 'string') detail = body.detail
  } catch { /* not JSON */ }
  return new ApiError(res.status, detail)
}

/** Throws ApiError for any non-2xx answer, after triggering the /lock redirect on a 401. */
export async function checked(res: Response, path: string): Promise<Response> {
  if (res.ok) return res
  if (res.status === 401 && !NO_REDIRECT.has(path)) onUnauthorized?.()
  throw await errorFrom(res)
}

async function request<T>(method: string, path: string, body?: unknown, signal?: AbortSignal): Promise<T> {
  const init: RequestInit = { method, credentials: 'same-origin', signal, headers: { Accept: 'application/json' } }
  if (body instanceof FormData) init.body = body
  else if (body !== undefined) {
    init.body = JSON.stringify(body)
    init.headers = { ...init.headers, 'Content-Type': 'application/json' }
  }
  const res = await checked(await fetch(API_BASE + path, init), path)
  if (res.status === 204) return undefined as T
  const type = res.headers.get('content-type') ?? ''
  return (type.includes('json') ? await res.json() : await res.text()) as T
}

export const api = {
  get: <T>(path: string, signal?: AbortSignal) => request<T>('GET', path, undefined, signal),
  send: <T = void>(method: 'POST' | 'PUT' | 'PATCH' | 'DELETE', path: string, body?: unknown) => request<T>(method, path, body),
}
