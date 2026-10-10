import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { useNavigate, useParams } from 'react-router'
import { FileHeart, History, MessageSquarePlus, Pill, WalletCards, FlaskConical } from 'lucide-react'
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
        if (cid !== threadId) navigate(`/chat/${threadId}`, { replace: !cid })
      }
    },
    onDone: () => {
      void qc.invalidateQueries({ queryKey: keys.conversations(profileId) })
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
      <div className="chat__head">
        {!empty && <h1 className="sr-only">{conv.data?.title || t('nav.chat')}</h1>}
        <button type="button" className="chat__headbtn" onClick={() => setDrawer(true)} aria-haspopup="dialog">
          <History aria-hidden="true" strokeWidth={2} /><span>{t('chat.history')}</span>
        </button>
        {!empty && (
          <button type="button" className="chat__headbtn" onClick={newChat}>
            <MessageSquarePlus aria-hidden="true" strokeWidth={2} /><span>{t('chat.newChat')}</span>
          </button>
        )}
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
          <div className="chat__empty">
            <h1 className="chat__greeting">{boldName(t('chat.greeting', { name }), name)}</h1>
            <div className="chat__chips">
              {CHIPS.map(c => (
                <button key={c.key} type="button" className="chat__chip"
                  onClick={() => (c.photo ? composer.current?.openPhotos() : send({ text: t(c.key), files: [] }))}>
                  <c.icon aria-hidden="true" strokeWidth={2} /><span>{t(c.key)}</span>
                </button>
              ))}
            </div>
          </div>
        )}
      </MessageList>

      <Composer ref={composer} streaming={run.streaming} onSend={send} onStop={run.stop} />

      <HistoryDrawer open={drawer} onClose={() => setDrawer(false)} profileId={profileId} current={cid}
        onOpen={id => { setDrawer(false); navigate(`/chat/${id}`) }} onNew={newChat}
        onDeleted={id => { if (id === cid) newChat() }} />
    </div>
  )
}

/** The reference's mixed-weight title: the greeting in regular weight, the person's name bold. */
function boldName(text: string, name: string) {
  const i = name ? text.indexOf(name) : -1
  if (i < 0) return text
  return <>{text.slice(0, i)}<strong>{name}</strong>{text.slice(i + name.length)}</>
}
