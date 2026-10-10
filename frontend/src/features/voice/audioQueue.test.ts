import { expect, test, vi } from 'vitest'
import { createAudioQueue } from './audioQueue'

/** A fake AudioContext: decodeAudioData resolves in a caller-chosen order, sources record what played. */
function fakeCtx() {
  const started: string[] = []
  const stopped: string[] = []
  const resolvers = new Map<string, () => void>()
  const ctx = {
    currentTime: 0,
    destination: {},
    decodeAudioData(buf: ArrayBuffer) {
      const id = new TextDecoder().decode(buf)
      return new Promise(res => resolvers.set(id, () => res({ duration: 1, id })))
    },
    createBufferSource() {
      const src = {
        buffer: null as null | { id: string },
        onended: null as null | (() => void),
        connect() {},
        start() { started.push(src.buffer!.id) },
        stop() { stopped.push(src.buffer!.id) },
      }
      return src
    },
  }
  return { ctx: ctx as unknown as AudioContext, started, stopped, resolve: (id: string) => resolvers.get(id)?.() }
}

const b64 = (s: string) => btoa(s)
const flush = () => new Promise(r => setTimeout(r, 0))

test('plays seq 0, 1, 2 in order even when 2 arrives before 1', async () => {
  const f = fakeCtx()
  const q = createAudioQueue(() => f.ctx)
  q.push('r1', 0, b64('a0'))
  q.push('r1', 2, b64('a2'))
  q.push('r1', 1, b64('a1'))
  f.resolve('a2'); f.resolve('a0'); await flush()
  expect(f.started).toEqual(['a0'])
  f.resolve('a1'); await flush()
  expect(f.started).toEqual(['a0', 'a1', 'a2'])
  expect(q.playing).toBe(true)
})

test('stop() silences everything and drops late arrivals for the cancelled run', async () => {
  const f = fakeCtx()
  const onStart = vi.fn()
  const q = createAudioQueue(() => f.ctx, { onStart })
  q.push('r1', 0, b64('a0'))
  f.resolve('a0'); await flush()
  expect(onStart).toHaveBeenCalledWith('r1')
  q.push('r1', 1, b64('a1')) // decoding while stop lands
  q.stop()
  expect(f.stopped).toEqual(['a0'])
  expect(q.playing).toBe(false)
  f.resolve('a1'); await flush()
  q.push('r1', 2, b64('a2')); f.resolve('a2'); await flush() // a late chunk of the cancelled run
  expect(f.started).toEqual(['a0'])
  // a new run plays again from its own seq 0
  q.push('r2', 0, b64('b0')); f.resolve('b0'); await flush()
  expect(f.started).toEqual(['a0', 'b0'])
})

test('onIdle fires when the last source ends', async () => {
  const f = fakeCtx()
  const onIdle = vi.fn()
  const sources: { onended: null | (() => void) }[] = []
  const orig = f.ctx.createBufferSource.bind(f.ctx)
  ;(f.ctx as unknown as { createBufferSource: () => unknown }).createBufferSource = () => { const s = orig(); sources.push(s as never); return s }
  const q = createAudioQueue(() => f.ctx, { onIdle })
  q.push('r1', 0, b64('a0')); f.resolve('a0'); await flush()
  sources[0].onended?.()
  expect(onIdle).toHaveBeenCalledTimes(1)
  expect(q.playing).toBe(false)
})
