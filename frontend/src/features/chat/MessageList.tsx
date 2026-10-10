import { useEffect, useLayoutEffect, useRef, useState, type ReactNode } from 'react'
import { useT } from '../../i18n'
import { Message, type MessageView } from './Message'

const NEAR = 48

/**
 * The conversation's own scroll area. It follows the stream while the reader is at the bottom; once they
 * scroll up it stays put and offers a "Bagong mensahe ↓" pill in the flow, between the list and the composer.
 */
export function MessageList({ messages, onRetry, children }: { messages: MessageView[]; onRetry?: () => void; children?: ReactNode }) {
  const t = useT()
  const ref = useRef<HTMLDivElement>(null)
  const atBottom = useRef(true)
  const [behind, setBehind] = useState(false)

  const last = messages[messages.length - 1]
  const signature = `${messages.length}:${last?.text.length ?? 0}:${last?.steps.length ?? 0}:${last?.blocks.length ?? 0}:${last?.status ?? ''}`

  const toBottom = () => {
    const el = ref.current
    if (!el) return
    el.scrollTo?.({ top: el.scrollHeight })
    atBottom.current = true
    setBehind(false)
  }

  useLayoutEffect(() => {
    if (atBottom.current) toBottom()
    else setBehind(true)
  }, [signature])

  useEffect(() => {
    const el = ref.current
    if (!el) return
    const onScroll = () => {
      atBottom.current = el.scrollHeight - el.scrollTop - el.clientHeight < NEAR
      if (atBottom.current) setBehind(false)
    }
    el.addEventListener('scroll', onScroll, { passive: true })
    return () => el.removeEventListener('scroll', onScroll)
  }, [])

  const lastAssistant = [...messages].reverse().find(m => m.role === 'assistant')

  return (
    <>
      <div className="chat__scroll" ref={ref}>
        <div className="chat__list">
          {children}
          {messages.map(m => (
            <Message key={m.key} m={m} onRetry={m === lastAssistant ? onRetry : undefined} />
          ))}
        </div>
      </div>
      {behind && (
        <button type="button" className="chat__pill" onClick={toBottom}>{t('chat.newMessages')}</button>
      )}
    </>
  )
}
