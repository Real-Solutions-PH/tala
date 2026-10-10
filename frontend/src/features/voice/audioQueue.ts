// Gapless player for the CUSTOM `audio` events of a run (plan C3): decode each WAV, play strictly in seq order.

export type AudioQueueHooks = {
  /** The first chunk of a run started playing (the client's first_audio_played stamp). */
  onStart?: (runId: string) => void
  /** Nothing is playing and nothing decoded is waiting. */
  onIdle?: () => void
}

export type AudioQueue = {
  push(runId: string, seq: number, wavB64: string): void
  /** Stop every source now, forget the queue, and drop any later chunk of the current run. */
  stop(): void
  readonly playing: boolean
}

function b64ToArrayBuffer(b64: string): ArrayBuffer {
  const bin = atob(b64)
  const out = new Uint8Array(bin.length)
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i)
  return out.buffer
}

export function createAudioQueue(getCtx: () => AudioContext, hooks: AudioQueueHooks = {}): AudioQueue {
  let run: string | null = null
  let gen = 0 // bumps on stop and on a new run; a drain from an older generation gives up
  let next = 0
  let endAt = 0
  let started = false
  let draining = false
  const pending = new Map<number, Promise<AudioBuffer | null>>()
  const sources = new Set<AudioBufferSourceNode>()
  const cancelled = new Set<string>()

  const schedule = (buf: AudioBuffer, runId: string) => {
    const ctx = getCtx()
    const src = ctx.createBufferSource()
    src.buffer = buf
    src.connect(ctx.destination)
    const at = Math.max(ctx.currentTime, endAt)
    src.start(at)
    endAt = at + buf.duration
    sources.add(src)
    src.onended = () => {
      sources.delete(src)
      if (!sources.size && !pending.size) hooks.onIdle?.()
    }
    if (!started) { started = true; hooks.onStart?.(runId) }
  }

  const drain = async () => {
    if (draining) return
    draining = true
    const myGen = gen
    const myRun = run!
    try {
      while (pending.has(next)) {
        const buf = await pending.get(next)!
        if (gen !== myGen) return
        pending.delete(next)
        next++
        if (buf) schedule(buf, myRun)
      }
    } finally {
      if (gen === myGen) draining = false
    }
  }

  return {
    push(runId, seq, wavB64) {
      if (cancelled.has(runId)) return
      if (run !== runId) {
        gen++; run = runId; next = 0; started = false; draining = false; pending.clear()
      }
      if (pending.has(seq) || seq < next) return
      const decoded = getCtx().decodeAudioData(b64ToArrayBuffer(wavB64)).catch(() => null)
      pending.set(seq, decoded)
      void drain()
    },
    stop() {
      if (run) cancelled.add(run)
      gen++
      run = null
      draining = false
      pending.clear()
      for (const s of sources) { s.onended = null; try { s.stop() } catch { /* already stopped */ } }
      sources.clear()
      endAt = 0
    },
    get playing() { return sources.size > 0 || pending.size > 0 },
  }
}
