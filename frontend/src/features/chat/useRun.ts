// One chat run at a time: posts the turn, folds the AG-UI stream into the turn's RunState, and stops it.
import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from '../../api/client'
import { initialRun, runReducer, startRun, type RunState } from '../../api/agui'
import type { Block, Message, Source } from '../../api/types'

export type TurnInput = { text: string; files: File[]; audio?: Blob }
export type Turn = { key: string; input: TurnInput; run: RunState }

type Opts = { profileId: number | null; lang: string; onThread: (threadId: string) => void; onDone: () => void }

let seq = 0

export function useRun({ profileId, lang, onThread, onDone }: Opts) {
  const [turns, setTurns] = useState<Turn[]>([])
  const active = useRef<{ key: string; abort: AbortController; runId?: string } | null>(null)
  const cbs = useRef({ onThread, onDone })
  useEffect(() => { cbs.current = { onThread, onDone } })

  const patch = useCallback((key: string, f: (s: RunState) => RunState) =>
    setTurns(ts => ts.map(t => (t.key === key ? { ...t, run: f(t.run) } : t))), [])

  const send = useCallback(async (input: TurnInput, conversationId: string | undefined) => {
    if (profileId == null || active.current) return
    const key = `t${++seq}`
    const abort = new AbortController()
    active.current = { key, abort }
    setTurns(ts => [...ts, { key, input, run: { ...initialRun } }])

    const form = new FormData()
    form.set('profile_id', String(profileId))
    if (conversationId) form.set('conversation_id', conversationId)
    if (input.text) form.set('message', input.text)
    form.set('lang', lang)
    form.set('mode', input.audio ? 'voice' : 'text')
    form.set('speak', '0')
    for (const f of input.files) form.append('files', f)
    if (input.audio) form.set('audio', input.audio, 'voice.webm')

    const mine = () => active.current?.key === key
    let terminal = false
    try {
      await startRun(form, e => {
        if (!mine()) return // stopped: late frames are ignored
        if (e.type === 'RUN_STARTED') { active.current!.runId = e.runId; cbs.current.onThread(e.threadId) }
        if (e.type === 'RUN_ERROR' && e.code === 'cancelled') return // a quiet stop, not a failure
        if (e.type === 'RUN_ERROR' || e.type === 'RUN_FINISHED') terminal = true
        patch(key, s => runReducer(s, e))
      }, abort.signal)
      if (mine() && !terminal) patch(key, s => ({ ...s, status: 'interrupted' }))
    } catch {
      if (mine()) patch(key, s => ({ ...s, status: s.text ? 'interrupted' : 'failed', error: s.error ?? 'chat.sendFailed' }))
    } finally {
      if (mine()) { active.current = null; cbs.current.onDone() }
    }
  }, [profileId, lang, patch])

  const stop = useCallback(() => {
    const a = active.current
    if (!a) return
    active.current = null
    if (a.runId) api.send('POST', `/runs/${a.runId}/cancel`).catch(() => {})
    a.abort.abort()
    patch(a.key, s => ({ ...s, status: 'stopped' }))
    cbs.current.onDone()
  }, [patch])

  const reset = useCallback(() => {
    const a = active.current
    active.current = null
    a?.abort.abort()
    setTurns([])
  }, [])

  useEffect(() => () => active.current?.abort.abort(), [])

  const streaming = turns.some(t => t.run.status === 'streaming')
  return { turns, send, stop, reset, streaming }
}

/** History rows may carry blocks/steps/sources as JSON strings; anything unreadable becomes []. */
export function parseList<T>(v: unknown): T[] {
  if (Array.isArray(v)) return v as T[]
  if (typeof v === 'string') {
    try { const x = JSON.parse(v); return Array.isArray(x) ? x : [] } catch { return [] }
  }
  return []
}

export function normalizeMessage(m: Message): Message {
  return {
    ...m,
    content: m.content ?? '',
    blocks: parseList<Block>(m.blocks),
    steps: parseList<string>(m.steps).map(s => (typeof s === 'string' ? s : String((s as { name?: string }).name ?? ''))),
    sources: parseList<Source>(m.sources),
  }
}
