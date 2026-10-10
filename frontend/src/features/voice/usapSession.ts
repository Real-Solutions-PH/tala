// The Usap turn loop (spec §6): VAD speech end -> run with audio -> text and audio stream back -> listen again.
// Owns the client clocks (8 s no-reply watchdog, 60 s + 30 s silence) and barge-in. No React here, so the
// clocks can be tested with fake timers; UsapMode subscribes to it.
import type { AgUiEvent } from '../../api/agui'
import type { Key } from '../../i18n'
import { encodeWav } from './wav'

export const WATCHDOG_MS = 8_000
export const SILENCE_MS = 60_000
export const SILENCE_GRACE_MS = 30_000
const MAX_TIMINGS = 10

export type Phase = 'listening' | 'thinking' | 'speaking' | 'ended'

export type TurnTiming = {
  turn: number
  runId?: string
  /** Server stamps in ms from the server's turn start (CUSTOM timing). */
  stamps: Record<string, number>
  /** Client: speech end (VAD) to the first chunk actually playing. */
  firstAudioMs?: number
}

export type UsapState = {
  phase: Phase
  transcript: string
  reply: string
  error?: Key
  stillThere: boolean
  timings: TurnTiming[]
  conversationId?: string
}

export type QueueLike = { readonly playing: boolean; push(runId: string, seq: number, b64: string): void; stop(): void }

export type UsapDeps = {
  profileId: number
  lang: 'en' | 'tl'
  mode: 'usap' | 'listen'
  conversationId?: string
  startRun: (form: FormData, onEvent: (e: AgUiEvent) => void, signal: AbortSignal) => Promise<void>
  cancel: (runId: string) => Promise<void>
  queue: QueueLike
  onEnd: () => void
  now?: () => number
}

export function createUsapSession(deps: UsapDeps) {
  const now = deps.now ?? (() => Date.now())
  let state: UsapState = { phase: 'listening', transcript: '', reply: '', stillThere: false, timings: [], conversationId: deps.conversationId }
  const subs = new Set<() => void>()
  const set = (patch: Partial<UsapState>) => { state = { ...state, ...patch }; subs.forEach(f => f()) }

  let turn = 0
  let runId: string | undefined
  let runActive = false
  let abort: AbortController | null = null
  let lastAudio: Blob | null = null
  let speechEndAt = 0
  let gotOutput = false
  let watchdog: ReturnType<typeof setTimeout> | undefined
  let silence: ReturnType<typeof setTimeout> | undefined

  const clearWatchdog = () => { clearTimeout(watchdog); watchdog = undefined }
  const clearSilence = () => { clearTimeout(silence); silence = undefined }

  const armSilence = () => {
    clearSilence()
    silence = setTimeout(() => {
      set({ stillThere: true })
      silence = setTimeout(() => end(), SILENCE_GRACE_MS)
    }, SILENCE_MS)
  }

  const toListening = () => {
    if (state.phase === 'ended') return
    set({ phase: 'listening' })
    armSilence()
  }

  const updateTiming = (t: number, patch: Partial<Omit<TurnTiming, "turn">>) => {
    const timings = state.timings.slice()
    const i = timings.findIndex(x => x.turn === t)
    if (i === -1) timings.push({ stamps: {}, ...patch, turn: t })
    else timings[i] = { ...timings[i], ...patch, stamps: { ...timings[i].stamps, ...patch.stamps } }
    set({ timings: timings.slice(-MAX_TIMINGS) })
  }

  /** Stop whatever Kapiling is doing for this turn: audio, the fetch, and the server run. */
  const interrupt = () => {
    clearWatchdog()
    const wasBusy = runActive || deps.queue.playing
    deps.queue.stop()
    abort?.abort()
    abort = null
    runActive = false
    if (wasBusy && runId) void deps.cancel(runId).catch(() => {})
    turn++
  }

  const onEvent = (t: number) => (e: AgUiEvent) => {
    if (t !== turn) return // a stale event of an interrupted turn
    switch (e.type) {
      case 'RUN_STARTED':
        runId = e.runId
        set({ conversationId: e.threadId })
        updateTiming(t, { runId: e.runId })
        break
      case 'TEXT_MESSAGE_CONTENT':
        gotOutput = true; clearWatchdog()
        set({ reply: state.reply + e.delta })
        break
      case 'CUSTOM':
        if (e.name === 'transcript') {
          set({ transcript: e.value.text })
          if (!gotOutput) {
            clearWatchdog()
            watchdog = setTimeout(() => {
              if (t !== turn) return
              interrupt()
              set({ error: 'voice.noReply' })
              toListening()
            }, WATCHDOG_MS)
          }
        } else if (e.name === 'audio') {
          gotOutput = true; clearWatchdog()
          if (deps.mode === 'listen') break // listen-in answers on screen only
          if (runId) deps.queue.push(runId, e.value.seq, e.value.wav_b64)
          if (state.phase !== 'speaking') set({ phase: 'speaking' })
        } else if (e.name === 'timing') {
          updateTiming(t, { stamps: e.value })
        }
        break
      case 'RUN_ERROR':
        if (e.message !== 'errors.cancelled') set({ error: e.message as Key })
        clearWatchdog()
        break
      case 'RUN_FINISHED':
        clearWatchdog()
        break
    }
  }

  const send = (audio: Blob) => {
    clearSilence()
    clearWatchdog()
    const t = ++turn
    gotOutput = false
    runActive = true
    abort = new AbortController()
    set({ phase: 'thinking', transcript: '', reply: '', error: undefined, stillThere: false })
    const form = new FormData()
    form.set('profile_id', String(deps.profileId))
    form.set('lang', deps.lang)
    form.set('mode', deps.mode)
    form.set('speak', deps.mode === 'usap' ? '1' : '0')
    form.set('speech_end_client', String(speechEndAt))
    if (state.conversationId) form.set('conversation_id', state.conversationId)
    form.set('audio', new File([audio], 'speech.wav', { type: 'audio/wav' }))
    deps.startRun(form, onEvent(t), abort.signal).then(
      () => {
        if (t !== turn) return
        runActive = false
        if (!deps.queue.playing) toListening()
      },
      (err: unknown) => {
        if (t !== turn || (err instanceof DOMException && err.name === 'AbortError')) return
        runActive = false
        clearWatchdog()
        set({ error: 'errors.generic' })
        toListening()
      },
    )
  }

  function end() {
    clearSilence(); clearWatchdog()
    interrupt()
    set({ phase: 'ended', stillThere: false })
    deps.onEnd()
  }

  return {
    get state() { return state },
    subscribe(f: () => void) { subs.add(f); return () => { subs.delete(f) } },
    /** Begin (or, after end(), begin again: React StrictMode mounts effects twice). */
    start() { if (state.phase === "ended") set({ phase: "listening", error: undefined }); toListening() },
    /** VAD: the person began talking. Barge-in when Kapiling is busy. */
    speechStart() {
      if (state.phase === 'ended') return
      clearSilence()
      if (state.stillThere) set({ stillThere: false })
      if (runActive || deps.queue.playing) {
        interrupt()
        set({ phase: 'listening' })
      }
    },
    /** VAD: the person stopped talking (16 kHz samples). */
    speechEnd(samples: Float32Array) {
      if (state.phase === 'ended') return
      if (runActive || deps.queue.playing) interrupt()
      speechEndAt = now()
      lastAudio = encodeWav(samples)
      send(lastAudio)
    },
    /** VAD: speech too short to count; go back to the silence clock. */
    misfire() { if (state.phase === 'listening') armSilence() },
    retry() { if (lastAudio && state.phase !== 'ended') { interrupt(); speechEndAt = now(); send(lastAudio) } },
    /** The queue started the first chunk of a run. */
    audioStarted(rid: string) {
      if (rid !== runId) return
      updateTiming(turn, { firstAudioMs: now() - speechEndAt })
    },
    /** The queue ran dry; if the run is done, listen again. */
    audioIdle() { if (!runActive && state.phase === 'speaking') toListening() },
    end,
  }
}

export type UsapSession = ReturnType<typeof createUsapSession>
