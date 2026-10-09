// Client side of the AG-UI stream (plan C3): POST /api/runs, parse text/event-stream, fold events into RunState.
import { API_BASE, checked } from './client'
import type { AgUiEvent, Block, Source } from './types'

export type { AgUiEvent } from './types'

export type RunState = {
  threadId?: string
  runId?: string
  messageId?: string
  text: string
  steps: { name: string; done: boolean }[]
  blocks: Block[]
  sources: Source[]
  transcript?: string
  status: 'streaming' | 'complete' | 'stopped' | 'interrupted' | 'failed'
  /** An i18n key from RUN_ERROR, e.g. "errors.timeout". */
  error?: string
}

export const initialRun: RunState = Object.freeze({ text: '', steps: [], blocks: [], sources: [], status: 'streaming' }) as RunState

/** Pure reducer: every case returns a new object and never touches the previous state. */
export function runReducer(state: RunState, e: AgUiEvent): RunState {
  switch (e.type) {
    case 'RUN_STARTED':
      return { ...state, threadId: e.threadId, runId: e.runId, status: 'streaming' }
    case 'STEP_STARTED':
      return state.steps.some(s => s.name === e.stepName) ? state : { ...state, steps: [...state.steps, { name: e.stepName, done: false }] }
    case 'STEP_FINISHED':
      return state.steps.some(s => s.name === e.stepName)
        ? { ...state, steps: state.steps.map(s => (s.name === e.stepName ? { ...s, done: true } : s)) }
        : { ...state, steps: [...state.steps, { name: e.stepName, done: true }] }
    case 'TEXT_MESSAGE_START':
    case 'TEXT_MESSAGE_END':
      return state.messageId === e.messageId ? state : { ...state, messageId: e.messageId }
    case 'TEXT_MESSAGE_CONTENT':
      return { ...state, messageId: e.messageId, text: state.text + e.delta }
    case 'CUSTOM':
      switch (e.name) {
        case 'transcript': return { ...state, transcript: e.value.text }
        case 'block': return { ...state, blocks: [...state.blocks, e.value] }
        case 'sources': return { ...state, sources: e.value }
        default: return state // audio and timing are handled by the player and the demo panel
      }
    case 'RUN_ERROR':
      return { ...state, status: 'failed', error: e.message }
    case 'RUN_FINISHED':
      return { ...state, threadId: e.threadId, runId: e.runId, messageId: e.result.messageId, status: e.result.status }
    default:
      return state
  }
}

/** Incremental text/event-stream parser. Frames end with a blank line; `data:` lines are joined with "\n". */
export function createSseParser(onData: (data: string) => void) {
  let buf = ''
  let data: string[] = []

  const dispatch = () => {
    if (data.length) onData(data.join('\n'))
    data = []
  }
  const line = (l: string) => {
    if (l === '') return dispatch()
    if (l.startsWith(':')) return // comment / keep-alive
    const i = l.indexOf(':')
    const field = i === -1 ? l : l.slice(0, i)
    let value = i === -1 ? '' : l.slice(i + 1)
    if (value.startsWith(' ')) value = value.slice(1)
    if (field === 'data') data.push(value)
  }

  return {
    push(text: string) {
      buf += text
      for (;;) {
        const m = /\r\n|\n|\r/.exec(buf)
        if (!m) break
        // A lone trailing \r may be the first half of \r\n split across chunks: wait for more.
        if (m[0] === '\r' && m.index === buf.length - 1) break
        const l = buf.slice(0, m.index)
        buf = buf.slice(m.index + m[0].length)
        line(l)
      }
    },
    end() {
      if (buf) line(buf.replace(/\r$/, ''))
      buf = ''
      dispatch()
    },
  }
}

/**
 * Starts a run and calls `onEvent` for each AG-UI event as it arrives. Resolves when the stream ends.
 * Rejects with ApiError on a non-2xx answer (a 401 also sends the user to /lock), or with an AbortError
 * when `signal` is aborted.
 */
export async function startRun(form: FormData, onEvent: (e: AgUiEvent) => void, signal: AbortSignal): Promise<void> {
  const res = await checked(
    await fetch(`${API_BASE}/runs`, { method: 'POST', body: form, signal, credentials: 'same-origin', headers: { Accept: 'text/event-stream' } }),
    '/runs',
  )
  const parser = createSseParser(raw => {
    let e: AgUiEvent
    try { e = JSON.parse(raw) } catch { return } // a malformed frame is skipped, the stream goes on
    onEvent(e)
  })
  if (!res.body) return
  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  for (;;) {
    const { value, done } = await reader.read()
    if (done) break
    parser.push(decoder.decode(value, { stream: true }))
  }
  parser.push(decoder.decode())
  parser.end()
}
