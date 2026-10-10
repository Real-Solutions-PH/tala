import { useEffect, useRef, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { CircleAlert, CircleStop, RotateCcw, Volume2 } from 'lucide-react'
import { API_BASE } from '../../api/client'
import type { Block, Source } from '../../api/types'
import { Badge } from '../../components/Badge'
import { Button } from '../../components/Button'
import { useToast } from '../../components/Toast'
import { useLang, useT, type Key } from '../../i18n'
import { BlockView } from './blocks'
import { Sources } from './blocks/Sources'
import { StepList, type Step } from './StepList'

export type MessageView = {
  key: string
  role: 'user' | 'assistant'
  text: string
  status: 'streaming' | 'complete' | 'stopped' | 'interrupted' | 'failed'
  steps: Step[]
  blocks: Block[]
  sources: Source[]
  images?: string[]
  voice?: boolean
  error?: string
}

function Thumbs({ files }: { files: string[] }) {
  return <div className="msg__thumbs">{files.map((u, i) => <img key={i} src={u} alt="" />)}</div>
}

export function Message({ m, onRetry }: { m: MessageView; onRetry?: () => void }) {
  const t = useT()
  const [lang] = useLang()
  const toast = useToast()
  const [speaking, setSpeaking] = useState(false)
  const audio = useRef<HTMLAudioElement | null>(null)
  useEffect(() => () => audio.current?.pause(), [])

  if (m.role === 'user') {
    return (
      <div className="msg msg--user">
        {m.images && m.images.length > 0 && <Thumbs files={m.images} />}
        {m.text && <p>{m.text}</p>}
      </div>
    )
  }

  const streaming = m.status === 'streaming'
  const unfinished = m.status === 'interrupted' || m.status === 'failed'

  const readAloud = async () => {
    setSpeaking(true)
    try {
      const form = new FormData()
      form.set('text', m.text)
      form.set('lang', lang)
      const res = await fetch(`${API_BASE}/speak`, { method: 'POST', body: form, credentials: 'same-origin' })
      if (!res.ok) throw new Error(String(res.status))
      const url = URL.createObjectURL(await res.blob())
      audio.current?.pause()
      const a = new Audio(url)
      audio.current = a
      a.onended = () => URL.revokeObjectURL(url)
      await a.play()
    } catch {
      toast(t('chat.speakFailed'), 'error')
    } finally {
      setSpeaking(false)
    }
  }

  const errorText = m.error && /^(errors|chat)\./.test(m.error) ? t(m.error as Key) : null

  return (
    <article className="msg msg--assistant" aria-busy={streaming || undefined}>
      <StepList steps={m.steps} live={streaming} />
      {(m.text || streaming) && (
        <div className="msg__text">
          <ReactMarkdown remarkPlugins={[remarkGfm]} skipHtml>{m.text}</ReactMarkdown>
          {streaming && <span className="caret" aria-hidden="true" />}
        </div>
      )}
      {m.blocks.map((b, i) => <BlockView key={i} block={b} />)}
      <Sources sources={m.sources} />
      {m.status === 'stopped' && <div><Badge tone="info" icon={CircleStop}>{t('chat.stopped')}</Badge></div>}
      {unfinished && (
        <div className="msg__failed">
          <Badge tone="warn" icon={CircleAlert}>{t('chat.didntFinish')}</Badge>
          {errorText && <p className="msg__error">{errorText}</p>}
          {onRetry && <Button variant="secondary" icon={RotateCcw} onClick={onRetry}>{t('chat.retry')}</Button>}
        </div>
      )}
      {!streaming && m.text && (
        <Button variant="ghost" icon={Volume2} loading={speaking} onClick={readAloud} className="msg__speak">{t('chat.readAloud')}</Button>
      )}
    </article>
  )
}
