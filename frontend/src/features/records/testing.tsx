// Test helpers for the records screens: a fetch mock keyed by "METHOD /path" and a router with providers.
// Not imported by the app; it lives here (not in a *.test file) so several test files can share it.
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render } from '@testing-library/react'
import { createMemoryRouter, RouterProvider, type RouteObject } from 'react-router'
import { vi } from 'vitest'
import { ToastProvider } from '../../components/Toast'
import { I18nProvider, type Lang } from '../../i18n'
import { LockProvider, PROFILE_KEY } from '../lock/useLock'
import type { Observation } from '../../api/types'

export const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } })

export type Call = { method: string; url: string; path: string; body: unknown }
type Handler = (call: Call) => Response | Promise<Response>

/** Routes are "GET /api/x" (query string ignored). Unknown routes answer 404. Every call is recorded. */
export function mockFetch(handlers: Record<string, Handler>) {
  const calls: Call[] = []
  const fn = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input)
    const method = (init?.method ?? 'GET').toUpperCase()
    const path = url.split('?')[0]
    const raw = init?.body
    const body = typeof raw === 'string' ? JSON.parse(raw) : raw
    const call = { method, url, path, body }
    calls.push(call)
    const h = handlers[`${method} ${path}`]
    return h ? h(call) : json({ detail: 'errors.notFound' }, 404)
  })
  vi.stubGlobal('fetch', fn)
  return { fn, calls }
}

export function renderRoutes(routes: RouteObject[], path: string | { pathname: string; search?: string; state?: unknown }, lang: Lang = 'tl') {
  localStorage.setItem(PROFILE_KEY, '1')
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: 0 } } })
  const router = createMemoryRouter(routes, { initialEntries: [path] })
  const utils = render(
    <QueryClientProvider client={client}>
      <I18nProvider initialLang={lang}>
        <ToastProvider>
          <LockProvider><RouterProvider router={router} /></LockProvider>
        </ToastProvider>
      </I18nProvider>
    </QueryClientProvider>,
  )
  return { ...utils, router, client }
}

let nextId = 1
export function obs(code: string, value: number, date: string, extra: Partial<Observation> = {}): Observation {
  const base: Record<string, Partial<Observation>> = {
    fbs: { label: 'Fasting blood sugar', unit: 'mg/dL', ref_low: 70, ref_high: 100 },
    hba1c: { label: 'HbA1c', unit: '%', ref_low: 4, ref_high: 5.6 },
    bp_systolic: { label: 'Blood pressure (systolic)', unit: 'mmHg', ref_low: 90, ref_high: 120 },
    bp_diastolic: { label: 'Blood pressure (diastolic)', unit: 'mmHg', ref_low: 60, ref_high: 80 },
  }
  return {
    id: nextId++, code, label: code, value, value_text: null, unit: null, ref_low: null, ref_high: null, date,
    facility: null, document_id: null, status: 'confirmed', ...base[code], ...extra,
  }
}
