import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import type { AgUiEvent } from '../../api/agui'
import { createUsapSession, type UsapDeps } from './usapSession'

type Emit = (e: AgUiEvent) => void

function setup(over: Partial<UsapDeps> = {}) {
  let emit: Emit = () => {}
  let finish: () => void = () => {}
  let signal: AbortSignal | undefined
  const forms: FormData[] = []
  const queue = { playing: false, push: vi.fn(), stop: vi.fn(() => { queue.playing = false }) }
  const deps: UsapDeps = {
    profileId: 1, lang: 'tl', mode: 'usap',
    startRun: vi.fn((form: FormData, onEvent: Emit, s: AbortSignal) => {
      forms.push(form); emit = onEvent; signal = s
      return new Promise<void>((res, rej) => {
        finish = res
        s.addEventListener('abort', () => rej(new DOMException('aborted', 'AbortError')))
      })
    }),
    cancel: vi.fn(async () => {}),
    queue,
    onEnd: vi.fn(),
    ...over,
  }
  const s = createUsapSession(deps)
  return { s, deps, queue, forms, emit: (e: AgUiEvent) => emit(e), finish: () => finish(), signal: () => signal }
}

const speech = new Float32Array(1600)

beforeEach(() => { vi.useFakeTimers() })
afterEach(() => { vi.useRealTimers() })

test('speech end posts a WAV with mode, speak=1 and the client stamp', () => {
  const t = setup()
  t.s.start()
  t.s.speechEnd(speech)
  const f = t.forms[0]
  expect(f.get('mode')).toBe('usap')
  expect(f.get('speak')).toBe('1')
  expect(f.get('lang')).toBe('tl')
  expect(Number(f.get('speech_end_client'))).toBeGreaterThan(0)
  expect((f.get('audio') as File).type).toBe('audio/wav')
  expect(t.s.state.phase).toBe('thinking')
})

test('barge-in while a run is active stops audio, aborts and calls cancel', () => {
  const t = setup()
  t.s.start(); t.s.speechEnd(speech)
  t.emit({ type: 'RUN_STARTED', threadId: 'c1', runId: 'r1' })
  t.emit({ type: 'CUSTOM', name: 'audio', value: { seq: 0, wav_b64: 'AA==' } })
  t.queue.playing = true
  t.s.speechStart()
  expect(t.queue.stop).toHaveBeenCalled()
  expect(t.deps.cancel).toHaveBeenCalledWith('r1')
  expect(t.signal()!.aborted).toBe(true)
  expect(t.s.state.phase).toBe('listening')
})

test('barge-in while only audio is still playing also cancels', () => {
  const t = setup()
  t.s.start(); t.s.speechEnd(speech)
  t.emit({ type: 'RUN_STARTED', threadId: 'c1', runId: 'r1' })
  t.emit({ type: 'CUSTOM', name: 'audio', value: { seq: 0, wav_b64: 'AA==' } })
  t.emit({ type: 'RUN_FINISHED', threadId: 'c1', runId: 'r1', result: { messageId: 'm', status: 'complete' } })
  t.queue.playing = true
  t.s.speechStart()
  expect(t.queue.stop).toHaveBeenCalled()
  expect(t.deps.cancel).toHaveBeenCalledWith('r1')
})

test('speech start while just listening does not cancel anything', () => {
  const t = setup()
  t.s.start(); t.s.speechStart()
  expect(t.deps.cancel).not.toHaveBeenCalled()
})

test('the watchdog fires 8 s after the transcript when no audio or text came', () => {
  const t = setup()
  t.s.start(); t.s.speechEnd(speech)
  t.emit({ type: 'RUN_STARTED', threadId: 'c1', runId: 'r1' })
  t.emit({ type: 'CUSTOM', name: 'transcript', value: { text: 'Ano po ang gamot ko?' } })
  vi.advanceTimersByTime(7999)
  expect(t.s.state.error).toBeUndefined()
  vi.advanceTimersByTime(1)
  expect(t.s.state.error).toBe('voice.noReply')
  expect(t.deps.cancel).toHaveBeenCalledWith('r1')
  // Retry resends the same audio
  t.s.retry()
  expect(t.forms).toHaveLength(2)
  expect(t.s.state.error).toBeUndefined()
})

test('text before 8 s disarms the watchdog', () => {
  const t = setup()
  t.s.start(); t.s.speechEnd(speech)
  t.emit({ type: 'RUN_STARTED', threadId: 'c1', runId: 'r1' })
  t.emit({ type: 'CUSTOM', name: 'transcript', value: { text: 'x' } })
  vi.advanceTimersByTime(3000)
  t.emit({ type: 'TEXT_MESSAGE_CONTENT', messageId: 'm', delta: 'Losartan po.' })
  vi.advanceTimersByTime(10000)
  expect(t.s.state.error).toBeUndefined()
  expect(t.s.state.reply).toBe('Losartan po.')
})

test('60 s of listening asks "are you still there", then ends 30 s later', () => {
  const t = setup()
  t.s.start()
  vi.advanceTimersByTime(59_999)
  expect(t.s.state.stillThere).toBe(false)
  vi.advanceTimersByTime(1)
  expect(t.s.state.stillThere).toBe(true)
  vi.advanceTimersByTime(29_999)
  expect(t.deps.onEnd).not.toHaveBeenCalled()
  vi.advanceTimersByTime(1)
  expect(t.deps.onEnd).toHaveBeenCalled()
  expect(t.s.state.phase).toBe('ended')
})

test('speaking resets the silence clock, and it does not run while thinking', () => {
  const t = setup()
  t.s.start()
  vi.advanceTimersByTime(50_000)
  t.s.speechStart(); t.s.speechEnd(speech)
  vi.advanceTimersByTime(70_000) // thinking: the silence clock is off
  expect(t.s.state.stillThere).toBe(false)
})

test('start() after end() listens again (StrictMode mounts effects twice)', () => {
  const t = setup()
  t.s.start(); t.s.end(); t.s.start()
  expect(t.s.state.phase).toBe('listening')
  t.s.speechEnd(speech)
  expect(t.s.state.phase).toBe('thinking')
})

test('listen mode never queues audio', () => {
  const t = setup({ mode: 'listen' })
  t.s.start(); t.s.speechEnd(speech)
  expect(t.forms[0].get('mode')).toBe('listen')
  t.emit({ type: 'CUSTOM', name: 'audio', value: { seq: 0, wav_b64: 'AA==' } })
  expect(t.queue.push).not.toHaveBeenCalled()
})

test('timing events build the last 10 turns', async () => {
  const t = setup()
  t.s.start()
  for (let i = 0; i < 12; i++) {
    t.s.speechEnd(speech)
    t.emit({ type: 'RUN_STARTED', threadId: 'c1', runId: `r${i}` })
    t.emit({ type: 'CUSTOM', name: 'timing', value: { speech_end: 0, stt_done: 300 + i } })
    t.emit({ type: 'RUN_FINISHED', threadId: 'c1', runId: `r${i}`, result: { messageId: 'm', status: 'complete' } })
    t.finish(); await Promise.resolve()
  }
  expect(t.s.state.timings).toHaveLength(10)
  expect(t.s.state.timings.at(-1)!.stamps.stt_done).toBe(311)
})
