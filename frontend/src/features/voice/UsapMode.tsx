// Hands-free Usap (and the listen-in variant) — spec §6. Full screen over the shell: the character, one
// state word, the live transcript and reply, and one Tapusin button. Opened at /usap?mode=listen&cid=…
import { useEffect, useMemo, useRef, useSyncExternalStore } from 'react'
import { useNavigate, useSearchParams } from 'react-router'
import { startRun } from '../../api/agui'
import { API_BASE } from '../../api/client'
import { Loader, Mic, Volume2 } from 'lucide-react'
import { Button } from '../../components/Button'
import { useLang, useT } from '../../i18n'
import { useLock } from '../lock/useLock'
import { createAudioQueue } from './audioQueue'
import { TimingPanel } from './TimingPanel'
import { createUsapSession, type Phase } from './usapSession'
import { useVad } from './useVad'
import './usap.css'

const CORE = { listening: Mic, thinking: Loader, speaking: Volume2, ended: Mic } as const

/** The prototype's listening ring: 72 ticks around a blue circle holding the state's icon. */
function ListenRing({ phase }: { phase: Phase }) {
  const Icon = CORE[phase]
  const ticks = Array.from({ length: 72 }, (_, i) => {
    const a = (i / 72) * Math.PI * 2 - Math.PI / 2
    return { x1: 50 + 44 * Math.cos(a), y1: 50 + 44 * Math.sin(a), x2: 50 + 49 * Math.cos(a), y2: 50 + 49 * Math.sin(a) }
  })
  return (
    <span className="tring" aria-hidden="true">
      <svg viewBox="0 0 100 100">{ticks.map((k, i) => <line key={i} className="tk on" style={{ animationDelay: `${(i % 12) * 0.1}s` }} {...k} />)}</svg>
      <span className="core"><Icon strokeWidth={2} /></span>
    </span>
  )
}
const WORD = { listening: 'voice.listening', thinking: 'voice.thinking', speaking: 'voice.speaking', ended: 'voice.ended' } as const

async function cancelRun(runId: string) {
  await fetch(`${API_BASE}/runs/${encodeURIComponent(runId)}/cancel`, { method: 'POST', credentials: 'same-origin' })
}

export function UsapMode() {
  const t = useT()
  const [lang] = useLang()
  const { profileId } = useLock()
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const mode = params.get('mode') === 'listen' ? 'listen' : 'usap'
  const cid = params.get('cid') ?? undefined

  const ctxRef = useRef<AudioContext | null>(null)
  const getCtx = () => (ctxRef.current ??= new AudioContext())

  const session = useMemo(() => {
    const holder: { s?: ReturnType<typeof createUsapSession> } = {}
    const queue = createAudioQueue(getCtx, {
      onStart: rid => holder.s?.audioStarted(rid),
      onIdle: () => holder.s?.audioIdle(),
    })
    holder.s = createUsapSession({
      profileId: profileId ?? 0, lang, mode, conversationId: cid, startRun, cancel: cancelRun, queue,
      onEnd: () => {},
    })
    return holder.s
    // One session per mount: a language switch mid-session keeps the session.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const state = useSyncExternalStore(session.subscribe, () => session.state)

  useEffect(() => {
    session.start()
    if (import.meta.env.DEV) (window as unknown as { __usap?: unknown }).__usap = session
    return () => { session.end(); void ctxRef.current?.close(); ctxRef.current = null }
  }, [session])

  const vad = useVad({
    onSpeechStart: () => { void ctxRef.current?.resume(); session.speechStart() },
    onSpeechEnd: samples => session.speechEnd(samples),
    onMisfire: () => session.misfire(),
  }, state.phase === 'speaking', state.phase !== 'ended')

  const leave = () => {
    session.end()
    const id = state.conversationId ?? cid
    navigate(id ? `/chat/${id}` : '/chat')
  }

  const hint = mode === 'listen' ? t('voice.listenHint') : t('voice.sayHint')
  const showWord = vad === 'ready' || state.phase !== 'listening'

  return (
    <div className={`usap usap--${state.phase}`} role="dialog" aria-modal="true" aria-label={t('voice.usapTitle')}>
      {mode === 'listen' && (
        <div className="usap__banner" role="status">
          <span className="usap__dot" aria-hidden="true" />
          {t('chat.consultOn')}
        </div>
      )}
      <div className="usap__stage">
        <ListenRing phase={state.phase} />
        <p className="usap__word" aria-live="polite">
          {showWord ? t(WORD[state.phase]) : vad === 'denied' ? '' : t('voice.loadingMic')}
        </p>
        {vad === 'denied' && <p className="usap__alert" role="alert">{t('voice.micDenied')}</p>}

        {state.stillThere && (
          <div className="usap__prompt" role="alert">
            <p className="usap__prompt-q">{t('voice.stillThere')}</p>
            <p className="usap__prompt-hint">{t('voice.stillThereHint')}</p>
          </div>
        )}

        {state.error && (
          <div className="usap__alert" role="alert">
            <p>{t(state.error)}</p>
            <Button variant="secondary" onClick={() => session.retry()}>{t('voice.retry')}</Button>
          </div>
        )}

        <div className="usap__talk">
          {state.transcript
            ? <p className="usap__said"><span className="usap__label">{t('voice.youSaid')}</span>{state.transcript}</p>
            : !state.reply && state.phase === 'listening' && !state.error && <p className="usap__hint">{hint}</p>}
          {state.reply && (
            <p className="usap__reply"><span className="usap__label">{t('voice.replyLabel')}</span>{state.reply}</p>
          )}
        </div>
      </div>
      <TimingPanel timings={state.timings} />
      <div className="usap__foot">
        <Button variant="danger" size="lg" block className="usap__end" onClick={leave}>{t('voice.end')}</Button>
      </div>
    </div>
  )
}
