import { afterEach, describe, expect, test, vi } from 'vitest'
import { initialRun, runReducer, startRun, type AgUiEvent, type RunState } from './agui'
import { setOnUnauthorized } from './client'

const enc = new TextEncoder()

/** A fetch stub whose response body streams the given chunks (strings or raw bytes) one by one. */
function streamingFetch(chunks: (string | Uint8Array)[], status = 200) {
  return vi.fn(async (_url: string, _init?: RequestInit) => {
    const body = new ReadableStream<Uint8Array>({
      start(c) {
        for (const ch of chunks) c.enqueue(typeof ch === 'string' ? enc.encode(ch) : ch)
        c.close()
      },
    })
    return new Response(body, { status, headers: { 'content-type': 'text/event-stream' } })
  })
}

async function collect(chunks: (string | Uint8Array)[]) {
  const fetchMock = streamingFetch(chunks)
  vi.stubGlobal('fetch', fetchMock)
  const events: AgUiEvent[] = []
  await startRun(new FormData(), e => events.push(e), new AbortController().signal)
  return { events, fetchMock }
}

afterEach(() => { vi.unstubAllGlobals(); setOnUnauthorized(null) })

describe('startRun SSE parser', () => {
  test('parser handles a frame split across chunks', async () => {
    const { events } = await collect([
      'data: {"type":"TEXT_MESS',
      'AGE_CONTENT","messageId":"m","delta":"Lo"}\n\n',
    ])
    expect(events).toEqual([{ type: 'TEXT_MESSAGE_CONTENT', messageId: 'm', delta: 'Lo' }])
  })

  test('parses several frames in one chunk and a blank-line boundary split across chunks', async () => {
    const { events } = await collect([
      'data: {"type":"STEP_STARTED","stepName":"check_meds"}\n\ndata: {"type":"STEP_FINISHED","stepName":"check_meds"}\n',
      '\n',
    ])
    expect(events.map(e => e.type)).toEqual(['STEP_STARTED', 'STEP_FINISHED'])
  })

  test('joins multi-line data fields and accepts CRLF line endings', async () => {
    const { events } = await collect(['data: {"type":"TEXT_MESSAGE_CONTENT",\r\ndata: "messageId":"m","delta":"x"}\r\n\r\n'])
    expect(events).toEqual([{ type: 'TEXT_MESSAGE_CONTENT', messageId: 'm', delta: 'x' }])
  })

  test('decodes a multi-byte character split across chunks', async () => {
    const bytes = enc.encode('data: {"type":"TEXT_MESSAGE_CONTENT","messageId":"m","delta":"Ñ"}\n\n')
    const cut = bytes.indexOf(0xc3) + 1 // inside the two-byte Ñ
    const { events } = await collect([bytes.slice(0, cut), bytes.slice(cut)])
    expect(events).toEqual([{ type: 'TEXT_MESSAGE_CONTENT', messageId: 'm', delta: 'Ñ' }])
  })

  test('ignores comments and a trailing frame without a blank line is still delivered', async () => {
    const { events } = await collect([': keep-alive\n\n', 'data: {"type":"RUN_STARTED","threadId":"t","runId":"r"}'])
    expect(events).toEqual([{ type: 'RUN_STARTED', threadId: 't', runId: 'r' }])
  })

  test('POSTs the form to /api/runs', async () => {
    const form = new FormData()
    form.set('message', 'anong gamot ko')
    const fetchMock = streamingFetch([])
    vi.stubGlobal('fetch', fetchMock)
    await startRun(form, () => {}, new AbortController().signal)
    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe('/api/runs')
    expect(init?.method).toBe('POST')
    expect(init?.body).toBe(form)
  })

  test('a 401 calls the unauthorized handler and rejects', async () => {
    const onUnauth = vi.fn()
    setOnUnauthorized(onUnauth)
    vi.stubGlobal('fetch', vi.fn(async () => new Response('{"detail":"errors.locked"}', { status: 401 })))
    await expect(startRun(new FormData(), () => {}, new AbortController().signal)).rejects.toMatchObject({ status: 401 })
    expect(onUnauth).toHaveBeenCalledOnce()
  })
})

describe('runReducer', () => {
  const run = (events: object[], from: RunState = initialRun) => events.reduce<RunState>((s, e) => runReducer(s, e as AgUiEvent), from)

  test('reducer builds text, steps and blocks in order', () => {
    let s = initialRun
    for (const e of [{ type: 'RUN_STARTED', threadId: 't', runId: 'r' }, { type: 'STEP_STARTED', stepName: 'check_meds' },
      { type: 'STEP_FINISHED', stepName: 'check_meds' }, { type: 'TEXT_MESSAGE_CONTENT', messageId: 'm', delta: 'Lo' },
      { type: 'TEXT_MESSAGE_CONTENT', messageId: 'm', delta: 'sartan' }, { type: 'CUSTOM', name: 'block', value: { type: 'disclaimer' } },
      { type: 'RUN_FINISHED', threadId: 't', runId: 'r', result: { messageId: 'm2', status: 'complete' } }]) s = runReducer(s, e as AgUiEvent)
    expect(s).toMatchObject({ text: 'Losartan', steps: [{ name: 'check_meds', done: true }], blocks: [{ type: 'disclaimer' }], messageId: 'm2', status: 'complete' })
    expect(s.threadId).toBe('t')
    expect(s.runId).toBe('r')
  })

  test('RUN_ERROR keeps partial text and marks failed', () => {
    const s = run([{ type: 'RUN_STARTED', threadId: 't', runId: 'r' }, { type: 'TEXT_MESSAGE_CONTENT', messageId: 'm', delta: 'Heto po' },
      { type: 'RUN_ERROR', message: 'errors.timeout', code: 'timeout' }])
    expect(s).toMatchObject({ text: 'Heto po', status: 'failed', error: 'errors.timeout' })
  })

  test('dedupes steps by name and marks only the matching one done', () => {
    const s = run([{ type: 'STEP_STARTED', stepName: 'search_records' }, { type: 'STEP_STARTED', stepName: 'check_labs' },
      { type: 'STEP_STARTED', stepName: 'search_records' }, { type: 'STEP_FINISHED', stepName: 'search_records' }])
    expect(s.steps).toEqual([{ name: 'search_records', done: true }, { name: 'check_labs', done: false }])
  })

  test('stores transcript and sources, ignores audio and timing', () => {
    const src = { n: 1, chunk_id: 4, document_id: 2, title: 'CBC', page: 1, before: 'a', match: 'b', after: 'c' }
    const s = run([{ type: 'CUSTOM', name: 'transcript', value: { text: 'anong gamot ko' } },
      { type: 'CUSTOM', name: 'sources', value: [src] }, { type: 'CUSTOM', name: 'audio', value: { seq: 0, wav_b64: 'x' } },
      { type: 'CUSTOM', name: 'timing', value: { first_token: 1 } }, { type: 'TOOL_CALL_START', toolCallId: 'c', toolCallName: 'x' }])
    expect(s).toMatchObject({ transcript: 'anong gamot ko', sources: [src], blocks: [], text: '' })
  })

  test('is pure: never mutates the previous state', () => {
    const before = run([{ type: 'STEP_STARTED', stepName: 'check_meds' }])
    const frozen = structuredClone(before)
    run([{ type: 'STEP_FINISHED', stepName: 'check_meds' }, { type: 'CUSTOM', name: 'block', value: { type: 'disclaimer' } }], before)
    expect(before).toEqual(frozen)
    expect(initialRun).toEqual({ text: '', steps: [], blocks: [], sources: [], status: 'streaming' })
  })
})
