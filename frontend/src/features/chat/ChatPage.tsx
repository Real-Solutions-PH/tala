import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { useNavigate, useParams } from 'react-router'
import { HeartPulse, FileHeart, History, MessageSquarePlus, Pill, WalletCards, FlaskConical } from 'lucide-react'
import { keys, useConversation, useProfiles } from '../../api/queries'
import type { Message as ApiMessage } from '../../api/types'
import { Skeleton } from '../../components/Skeleton'
import { useLang, useT, type Key } from '../../i18n'
import { useLock } from '../lock/useLock'
import { Composer, type ComposerHandle } from './Composer'
import { HistoryDrawer } from './HistoryDrawer'
import type { MessageView } from './Message'
import { MessageList } from './MessageList'
import { normalizeMessage, useRun, type Turn, type TurnInput } from './useRun'
import './chat.css'

const objectUrl = (f: Blob) => (typeof URL.createObjectURL === 'function' ? URL.createObjectURL(f) : '')

function fromHistory(m: ApiMessage): MessageView {
  const n = normalizeMessage(m)
  return {
    key: n.id, role: n.role, text: n.content, status: n.status ?? 'complete',
    steps: n.steps.filter(Boolean).map(name => ({ name, done: true })), blocks: n.blocks, sources: n.sources,
    voice: n.mode === 'voice',
  }
}

function fromTurn(turn: Turn, images: string[]): MessageView[] {
  const r = turn.run
  return [
    { key: `${turn.key}-u`, role: 'user', text: turn.input.text || r.transcript || '', status: 'complete', steps: [], blocks: [], sources: [], images, voice: !!turn.input.audio },
    { key: `${turn.key}-a`, role: 'assistant', text: r.text, status: r.status, steps: r.steps, blocks: r.blocks, sources: r.sources, error: r.error },
  ]
}

const CHIPS: { key: Key; icon: typeof Pill; photo?: boolean }[] = [
  { key: 'chat.chipPhilhealth', icon: WalletCards },
  { key: 'chat.chipMeds', icon: Pill },
  { key: 'chat.chipLatest', icon: FlaskConical },
  { key: 'chat.chipForm', icon: FileHeart, photo: true },
]

export function ChatPage() {
  const t = useT()
  const [lang] = useLang()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const { cid } = useParams()
  const { profileId } = useLock()
  const me = useProfiles().data?.find(p => p.id === profileId)
  const name = me ? (me.nickname ?? me.full_name) : ''
  const conv = useConversation(cid)
  const composer = useRef<ComposerHandle>(null)
  const [drawer, setDrawer] = useState(false)

  // The conversation the live turns belong to. A ref, so a navigate() from RUN_STARTED is seen at once.
  const liveCid = useRef<string | undefined>(undefined)
  const [base, setBase] = useState<MessageView[]>([])

  const run = useRun({
    profileId, lang,
    onThread: threadId => {
      if (liveCid.current !== threadId) {
        liveCid.current = threadId
        if (cid !== threadId) navigate(`/chat/${threadId}`, { replace: true })
      }
    },
    onDone: () => {
      void qc.invalidateQueries({ queryKey: keys.conversations(profileId) })
      // Refetch the saved conversation so it is all there when the reader comes back from a card or document.
      if (liveCid.current) void qc.invalidateQueries({ queryKey: keys.conversation(liveCid.current) })
    },
  })
  const { reset } = run

  // Leaving for another conversation (history, back button, new chat) drops the live turns.
  useEffect(() => {
    if (liveCid.current !== cid) { liveCid.current = cid; reset(); setBase([]) }
  }, [cid, reset])

  // Thumbnail URLs are made once per turn (not per streamed token).
  const urlCache = useRef(new Map<string, string[]>())
  const imagesOf = (tn: Turn) => {
    let u = urlCache.current.get(tn.key)
    if (!u) { u = tn.input.files.map(objectUrl); urlCache.current.set(tn.key, u) }
    return u
  }
  const live = run.turns.length > 0
  const history = useMemo(() => (conv.data?.messages ?? []).map(fromHistory), [conv.data])
  const messages: MessageView[] = live ? [...base, ...run.turns.flatMap(tn => fromTurn(tn, imagesOf(tn)))] : (cid ? history : [])

  const send = useCallback((input: TurnInput) => {
    if (!live) { setBase(cid ? history : []); liveCid.current = cid }
    void run.send(input, cid)
  }, [live, cid, history, run])

  const retry = useCallback(() => {
    const lastTurn = run.turns[run.turns.length - 1]
    if (lastTurn) return send(lastTurn.input)
    const lastUser = [...messages].reverse().find(m => m.role === 'user')
    if (lastUser?.text) send({ text: lastUser.text, files: [] })
  }, [run.turns, messages, send])

  const newChat = () => { setDrawer(false); reset(); setBase([]); liveCid.current = undefined; navigate('/chat') }

  const loading = !!cid && !live && conv.isPending
  const empty = !cid && !live

  return (
    <div className="chat">
      {!empty && <h1 className="sr-only">{conv.data?.title || t('nav.chat')}</h1>}
      {/* The prototype's consultation bar: the switch opens listen-in (Usap's listening mode) for this conversation. */}
      <div className="chat__top">
        <div className="consult">
          <span className="consult__lbl"><span className="recdot" aria-hidden="true" />{t('chat.consult')}</span>
          <button type="button" className="switch" role="switch" aria-checked="false" aria-label={t('chat.consult')}
            onClick={() => navigate(`/usap?mode=listen${cid ? `&cid=${cid}` : ''}`)} />
        </div>
        <div className="chat__minis">
          <button type="button" className="mini" onClick={() => setDrawer(true)} aria-haspopup="dialog">
            <History aria-hidden="true" strokeWidth={2} /><span>{t('chat.historyShort')}</span>
          </button>
          {!empty && (
            <button type="button" className="mini" onClick={newChat}>
              <MessageSquarePlus aria-hidden="true" strokeWidth={2} /><span>{t('chat.newShort')}</span>
            </button>
          )}
        </div>
      </div>

      <MessageList messages={messages} onRetry={run.streaming ? undefined : retry}>
        {loading && (
          <div className="chat-skeleton" aria-busy="true" aria-label={t('common.loading')}>
            <Skeleton width="60%" height={48} radius={20} className="chat-skeleton__user" />
            <Skeleton height={20} /><Skeleton width="85%" height={20} /><Skeleton width="70%" height={20} />
            <Skeleton width="50%" height={48} radius={20} className="chat-skeleton__user" />
            <Skeleton height={20} /><Skeleton width="80%" height={20} />
          </div>
        )}
        {empty && (
          <article className="msg msg--assistant chat__hello">
            <h1 className="sr-only">{t('chat.greeting', { name })}</h1>
            <div className="from"><HeartPulse aria-hidden="true" strokeWidth={2} />{t('chat.from')}</div>
            <div className="msg__text"><p>{t('chat.botHello')}</p></div>
          </article>
        )}
      </MessageList>

      {/* Suggested questions: a sideways row of pills, as in the prototype. */}
      <div className="suggest" role="group" aria-label={t('chat.suggestions')}>
        {CHIPS.map(c => (
          <button key={c.key} type="button" className="sug" disabled={run.streaming}
            onClick={() => (c.photo ? composer.current?.openPhotos() : send({ text: t(c.key), files: [] }))}>{t(c.key)}</button>
        ))}
      </div>

      <Composer ref={composer} streaming={run.streaming} onSend={send} onStop={run.stop} />

      <HistoryDrawer open={drawer} onClose={() => setDrawer(false)} profileId={profileId} current={cid}
        onOpen={id => { setDrawer(false); navigate(`/chat/${id}`) }} onNew={newChat}
        onDeleted={id => { if (id === cid) newChat() }} />
    </div>
  )
}
