import { act, cleanup, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router'
import { afterEach, beforeAll, beforeEach, describe, expect, test, vi } from 'vitest'
import type { AgUiEvent, Block, Source } from '../../api/types'
import { ToastProvider } from '../../components/Toast'
import { I18nProvider, type Lang } from '../../i18n'
import { routes } from '../../routes'
import { json, mockFetch, renderRoutes } from '../records/testing'
import { BlockView } from './blocks'
import { Sources } from './blocks/Sources'

const PROFILES = [{ id: 1, nickname: 'Lola Remy', full_name: 'Remedios Santos', photo_url: null }]
const SUMMARY = { profile: { id: 1 }, conditions: [], allergies: [], meds: [], latest: {}, contacts: [] }
const CONVS = [
  { id: 'c1', title: 'Gamot ko', updated: new Date().toISOString() },
  { id: 'c0', title: 'Lumang usapan', updated: '2026-01-01T00:00:00Z' },
]

/** An SSE response whose frames the test pushes one at a time. */
function sseStream() {
  let ctrl!: ReadableStreamDefaultController<Uint8Array>
  const enc = new TextEncoder()
  const body = new ReadableStream<Uint8Array>({ start(c) { ctrl = c } })
  return {
    response: () => new Response(body, { status: 200, headers: { 'content-type': 'text/event-stream' } }),
    push: async (e: AgUiEvent) => { await act(async () => { ctrl.enqueue(enc.encode(`data: ${JSON.stringify(e)}\n\n`)); await new Promise(r => setTimeout(r, 10)) }) },
    close: async () => { await act(async () => { ctrl.close(); await new Promise(r => setTimeout(r, 10)) }) },
  }
}

function base(extra: Parameters<typeof mockFetch>[0] = {}) {
  return mockFetch({
    'GET /api/profiles': () => json(PROFILES),
    'GET /api/profiles/1/summary': () => json(SUMMARY),
    'GET /api/profiles/1/conversations': () => json(CONVS),
    ...extra,
  })
}

async function send(text: string) {
  await userEvent.type(await screen.findByRole('textbox', { name: /Mag-type dito/ }), text)
  await userEvent.click(screen.getByRole('button', { name: 'Ipadala' }))
}

beforeAll(() => {
  const proto = HTMLDialogElement.prototype as HTMLDialogElement & { showModal: () => void; close: () => void }
  proto.showModal = function (this: HTMLDialogElement) { this.setAttribute('open', '') }
  proto.close = function (this: HTMLDialogElement) { this.removeAttribute('open'); this.dispatchEvent(new Event('close')) }
  Element.prototype.scrollTo = function () {}
})
beforeEach(() => { localStorage.clear() })
afterEach(() => { cleanup(); vi.unstubAllGlobals() })

describe('ChatPage', () => {
  test('empty chat greets by nickname with 4 quick chips', async () => {
    base()
    renderRoutes(routes, '/chat')
    expect(await screen.findByRole('heading', { name: /Magandang araw po, Lola Remy/ })).toBeTruthy()
    for (const name of ['Ipakita ang PhilHealth', 'Mga gamot ko', 'Huling resulta', 'Sagutan ang form'])
      expect(screen.getByRole('button', { name })).toBeTruthy()
  })

  test('a scripted stream shows the steps, then the text, then collapses the steps', async () => {
    const s = sseStream()
    const { calls } = base({ 'POST /api/runs': () => s.response() })
    const { router } = renderRoutes(routes, '/chat')
    await send('Ano ang gamot ko?')
    await waitFor(() => expect(calls.some(c => c.method === 'POST' && c.path === '/api/runs')).toBe(true))
    const form = calls.find(c => c.path === '/api/runs')!.body as FormData
    expect(form.get('message')).toBe('Ano ang gamot ko?')
    expect(form.get('profile_id')).toBe('1')
    expect(form.get('mode')).toBe('text')
    expect(screen.getByText('Ano ang gamot ko?')).toBeTruthy()

    await s.push({ type: 'RUN_STARTED', threadId: 'c9', runId: 'r1' })
    await s.push({ type: 'STEP_STARTED', stepName: 'check_meds' })
    expect(screen.getAllByText('Tinitingnan ang mga gamot ninyo…').length).toBeGreaterThan(0)
    await s.push({ type: 'STEP_FINISHED', stepName: 'check_meds' })
    await s.push({ type: 'TEXT_MESSAGE_START', messageId: 'm1', role: 'assistant' })
    await s.push({ type: 'TEXT_MESSAGE_CONTENT', messageId: 'm1', delta: 'Ito po ang **mga gamot** ninyo.' })
    expect(screen.getByText('mga gamot')).toBeTruthy()
    expect(screen.queryByText('1 hakbang')).toBeNull()
    await s.push({ type: 'CUSTOM', name: 'block', value: { type: 'disclaimer' } })
    await s.push({ type: 'RUN_FINISHED', threadId: 'c9', runId: 'r1', result: { messageId: 'm1', status: 'complete' } })
    await s.close()
    expect(await screen.findByText('1 hakbang')).toBeTruthy()
    expect(screen.getByText(/Paalala/, { selector: 'p' })).toBeTruthy()
    expect(router.state.location.pathname).toBe('/chat/c9')
  })

  test('Stop posts cancel and shows "Itinigil"', async () => {
    const s = sseStream()
    const { calls } = base({ 'POST /api/runs': () => s.response(), 'POST /api/runs/r1/cancel': () => new Response(null, { status: 204 }) })
    renderRoutes(routes, '/chat')
    await send('Kumusta')
    await s.push({ type: 'RUN_STARTED', threadId: 'c9', runId: 'r1' })
    await s.push({ type: 'TEXT_MESSAGE_CONTENT', messageId: 'm1', delta: 'Sandali po' })
    await userEvent.click(screen.getByRole('button', { name: 'Itigil' }))
    await waitFor(() => expect(calls.some(c => c.method === 'POST' && c.path === '/api/runs/r1/cancel')).toBe(true))
    expect(await screen.findByText('Itinigil')).toBeTruthy()
    expect(screen.getByText('Sandali po')).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Boses' })).toBeTruthy()
  })

  test('a stream that ends without RUN_FINISHED shows "Hindi natapos" and Retry resends', async () => {
    const streams = [sseStream(), sseStream()]
    let i = 0
    const { calls } = base({ 'POST /api/runs': () => streams[i++].response() })
    renderRoutes(routes, '/chat')
    await send('Huling resulta ko')
    await streams[0].push({ type: 'RUN_STARTED', threadId: 'c9', runId: 'r1' })
    await streams[0].push({ type: 'TEXT_MESSAGE_CONTENT', messageId: 'm1', delta: 'Kalahati' })
    await streams[0].close()
    expect(await screen.findByText('Hindi natapos')).toBeTruthy()
    expect(screen.getByText('Kalahati')).toBeTruthy()
    await userEvent.click(screen.getByRole('button', { name: 'Subukan muli' }))
    await waitFor(() => expect(calls.filter(c => c.path === '/api/runs')).toHaveLength(2))
    expect((calls.filter(c => c.path === '/api/runs')[1].body as FormData).get('message')).toBe('Huling resulta ko')
  })

  test('opening /chat/:cid shows a skeleton before the messages arrive', async () => {
    let resolve!: (r: Response) => void
    base({ 'GET /api/conversations/c1': () => new Promise<Response>(r => { resolve = r }) })
    renderRoutes(routes, '/chat/c1')
    await waitFor(() => expect(document.querySelector('.chat-skeleton')).toBeTruthy())
    expect(screen.queryByText(/Magandang araw po/)).toBeNull()
    await act(async () => {
      resolve(json({
        id: 'c1', title: 'Gamot ko', messages: [
          { id: 'u1', role: 'user', content: 'Ano ang gamot ko?', mode: 'text', status: 'complete', blocks: '[]', steps: '[]', sources: '[]', attachments: [], created: '' },
          { id: 'a1', role: 'assistant', content: 'Metformin po.', mode: 'text', status: 'complete', blocks: JSON.stringify([{ type: 'disclaimer' }]), steps: JSON.stringify(['check_meds']), sources: 'not json', attachments: [], created: '' },
        ],
      }))
    })
    expect(await screen.findByText('Metformin po.')).toBeTruthy()
    expect(screen.getByText('Ano ang gamot ko?')).toBeTruthy()
    expect(screen.getByText('1 hakbang')).toBeTruthy()
    expect(document.querySelector('.chat-skeleton')).toBeNull()
  })

  test('one primary button: Boses when empty, Ipadala with text, Itigil while streaming', async () => {
    const s = sseStream()
    base({ 'POST /api/runs': () => s.response() })
    renderRoutes(routes, '/chat')
    const box = await screen.findByRole('textbox', { name: /Mag-type dito/ })
    expect(screen.getByRole('button', { name: 'Boses' })).toBeTruthy()
    expect(screen.queryByRole('button', { name: 'Ipadala' })).toBeNull()
    expect(screen.getByRole('button', { name: 'Magdagdag ng litrato' })).toBeTruthy()
    await userEvent.type(box, 'Kumusta')
    expect(screen.getByRole('button', { name: 'Ipadala' })).toBeTruthy()
    expect(screen.queryByRole('button', { name: 'Boses' })).toBeNull()
    await userEvent.clear(box)
    expect(screen.getByRole('button', { name: 'Boses' })).toBeTruthy()
    await send('Kumusta')
    await s.push({ type: 'RUN_STARTED', threadId: 'c9', runId: 'r1' })
    expect(screen.getByRole('button', { name: 'Itigil' })).toBeTruthy()
    expect(screen.queryByRole('button', { name: 'Boses' })).toBeNull()
    expect(screen.queryByRole('button', { name: 'Ipadala' })).toBeNull()
  })

  test('closing a card opened from chat returns to the same conversation', async () => {
    const card = { id: 5, kind: 'philhealth', label: 'PhilHealth', number_masked: null, front_url: '/api/files/5/front', back_url: null, expires: null }
    base({
      'GET /api/profiles/1/cards': () => json([card]),
      'GET /api/conversations/c1': () => json({
        id: 'c1', title: 'PhilHealth', messages: [
          { id: 'u1', role: 'user', content: 'Ipakita ang PhilHealth', mode: 'text', status: 'complete', blocks: '[]', steps: '[]', sources: '[]', attachments: [], created: '' },
          { id: 'a1', role: 'assistant', content: 'Ito po ang PhilHealth card ninyo.', mode: 'text', status: 'complete', blocks: JSON.stringify([{ type: 'card', card_id: 5, label: 'PhilHealth', front_url: '/api/files/5/front', back_url: null }]), steps: '[]', sources: '[]', attachments: [], created: '' },
        ],
      }),
    })
    const { router } = renderRoutes(routes, '/chat/c1')
    await userEvent.click(await screen.findByRole('link', { name: /Ipakita ang card/ }))
    await waitFor(() => expect(router.state.location.pathname).toBe('/cards/5'))
    await userEvent.click(await screen.findByRole('button', { name: 'Isara' }))
    await waitFor(() => expect(router.state.location.pathname).toBe('/chat/c1'))
    expect(await screen.findByText('Ito po ang PhilHealth card ninyo.')).toBeTruthy()
    expect(screen.getByText('Ipakita ang PhilHealth')).toBeTruthy()
  })

  test('history rename sends PATCH and toasts', async () => {
    const { calls } = base({ 'PATCH /api/conversations/c1': () => new Response(null, { status: 204 }) })
    renderRoutes(routes, '/chat')
    await userEvent.click(await screen.findByRole('button', { name: 'Kasaysayan' }))
    const dialog = await screen.findByRole('dialog', { name: 'Mga nakaraang usapan' })
    expect(await within(dialog).findByText('Gamot ko')).toBeTruthy()
    await userEvent.click(within(dialog).getByRole('button', { name: 'Mga pagpipilian para sa Gamot ko' }))
    await userEvent.click(within(dialog).getByRole('button', { name: 'Palitan ang pangalan' }))
    const input = within(dialog).getByRole('textbox', { name: 'Bagong pangalan' })
    await userEvent.clear(input)
    await userEvent.type(input, 'Mga gamot ni Lola')
    await userEvent.click(within(dialog).getByRole('button', { name: 'I-save' }))
    await waitFor(() => expect(calls.some(c => c.method === 'PATCH' && c.path === '/api/conversations/c1')).toBe(true))
    expect(calls.find(c => c.method === 'PATCH')!.body).toEqual({ title: 'Mga gamot ni Lola' })
    expect(await screen.findByText('Napalitan ang pangalan ng usapan.')).toBeTruthy()
  }, 20_000)
})

function renderBlock(block: Block, lang: Lang = 'tl') {
  return render(<I18nProvider initialLang={lang}><ToastProvider><MemoryRouter><BlockView block={block} /></MemoryRouter></ToastProvider></I18nProvider>)
}

describe('blocks', () => {
  test('the disclaimer renders the catalogue text in the current language', () => {
    renderBlock({ type: 'disclaimer' }, 'en')
    expect(screen.getByText(/Reminder: This is not medical advice/)).toBeTruthy()
    cleanup()
    renderBlock({ type: 'disclaimer' }, 'tl')
    expect(screen.getByText(/Paalala/, { selector: 'p' })).toBeTruthy()
  })

  test('the refusal block renders the catalogue refusal text', () => {
    renderBlock({ type: 'refusal', kind: 'medication' }, 'en')
    expect(screen.getByText(/I can’t give advice about medicines/)).toBeTruthy()
    cleanup()
    renderBlock({ type: 'refusal', kind: 'diagnosis' }, 'en')
    expect(screen.getByText(/I can’t give a diagnosis/)).toBeTruthy()
  })

  test('form answers show "Wala sa record" for null answers', () => {
    renderBlock({ type: 'form_answers', items: [{ field: 'Blood type', answer: 'O+', source: null }, { field: 'Last tetanus shot', answer: null, source: null }] })
    expect(screen.getByText('O+')).toBeTruthy()
    expect(screen.getByText(/Wala sa record/)).toBeTruthy()
  })

  test('source chips link to the document route', () => {
    const src: Source[] = [{ n: 1, chunk_id: 42, document_id: 7, title: 'CBC result', page: 1, before: 'a', match: 'b', after: 'c' }]
    render(<I18nProvider initialLang="tl"><MemoryRouter><Sources sources={src} /></MemoryRouter></I18nProvider>)
    const link = screen.getByRole('link', { name: /CBC result/ })
    expect(link.getAttribute('href')).toBe('/records/documents/7?chunk=42')
    expect(link.textContent).toContain('1')
  })
})
