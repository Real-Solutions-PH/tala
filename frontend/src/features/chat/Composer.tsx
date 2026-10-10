import { useEffect, useImperativeHandle, useMemo, useRef, useState, type Ref } from 'react'
import { Camera, Mic, Send, Square, X } from 'lucide-react'
import { useT } from '../../i18n'
import type { TurnInput } from './useRun'

export type ComposerHandle = { openPhotos: () => void }

type Props = {
  streaming: boolean
  onSend: (input: TurnInput) => void
  onStop: () => void
  ref?: Ref<ComposerHandle>
}

const MAX_LINES = 4

const objectUrl = (f: Blob) => (typeof URL.createObjectURL === 'function' ? URL.createObjectURL(f) : '')

/** One plane above the bottom menu: text, photos, push-to-talk (Boses) and Send, which becomes Stop. */
export function Composer({ streaming, onSend, onStop, ref }: Props) {
  const t = useT()
  const [text, setText] = useState('')
  const [files, setFiles] = useState<File[]>([])
  const [recording, setRecording] = useState(false)
  const area = useRef<HTMLTextAreaElement>(null)
  const picker = useRef<HTMLInputElement>(null)
  const recorder = useRef<MediaRecorder | null>(null)

  useImperativeHandle(ref, () => ({ openPhotos: () => picker.current?.click() }), [])

  const thumbs = useMemo(() => files.map(objectUrl), [files])
  useEffect(() => () => thumbs.forEach(u => u && URL.revokeObjectURL(u)), [thumbs])

  // Grow with the text up to four lines, then scroll inside.
  useEffect(() => {
    const el = area.current
    if (!el) return
    el.style.height = 'auto'
    const lh = parseFloat(getComputedStyle(el).lineHeight) || 24
    const pad = parseFloat(getComputedStyle(el).paddingTop || '0') * 2
    const max = lh * MAX_LINES + pad
    el.style.height = `${Math.min(el.scrollHeight, max) || ''}px`
    el.style.overflowY = el.scrollHeight > max ? 'auto' : 'hidden'
  }, [text])

  const canSend = !streaming && (text.trim().length > 0 || files.length > 0)

  const submit = () => {
    if (!canSend) return
    onSend({ text: text.trim(), files })
    setText('')
    setFiles([])
  }

  const startVoice = async () => {
    if (streaming || recording || typeof MediaRecorder === 'undefined' || !navigator.mediaDevices?.getUserMedia) return
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const rec = new MediaRecorder(stream)
      const chunks: Blob[] = []
      rec.ondataavailable = e => { if (e.data.size) chunks.push(e.data) }
      rec.onstop = () => {
        stream.getTracks().forEach(tr => tr.stop())
        setRecording(false)
        if (chunks.length) onSend({ text: '', files, audio: new Blob(chunks, { type: rec.mimeType || 'audio/webm' }) })
        setFiles([])
      }
      recorder.current = rec
      rec.start()
      setRecording(true)
    } catch {
      setRecording(false)
    }
  }
  const stopVoice = () => {
    if (recorder.current?.state === 'recording') recorder.current.stop()
    recorder.current = null
  }

  return (
    <form className="composer" onSubmit={e => { e.preventDefault(); submit() }}>
      {files.length > 0 && (
        <ul className="composer__thumbs">
          {files.map((f, i) => (
            <li key={`${f.name}-${i}`}>
              {thumbs[i] ? <img src={thumbs[i]} alt="" /> : <span className="composer__thumb-ph" />}
              <button type="button" className="composer__remove" aria-label={t('chat.removePhoto', { n: i + 1 })}
                onClick={() => setFiles(fs => fs.filter((_, j) => j !== i))}>
                <X aria-hidden="true" />
              </button>
            </li>
          ))}
        </ul>
      )}
      {recording && <p className="composer__recording" role="status">{t('chat.recording')}</p>}
      <div className="composer__row">
        <textarea ref={area} className="composer__input" rows={1} value={text} aria-label={t('chat.placeholder')}
          placeholder={t('chat.placeholder')} onChange={e => setText(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); submit() } }} />
      </div>
      <div className="composer__actions">
        <input ref={picker} type="file" accept="image/*" multiple hidden
          onChange={e => { const fs = Array.from(e.target.files ?? []); if (fs.length) setFiles(p => [...p, ...fs]); e.target.value = '' }} />
        <button type="button" className="composer__btn" onClick={() => picker.current?.click()} disabled={streaming}>
          <Camera aria-hidden="true" strokeWidth={2} /><span>{t('chat.photo')}</span>
        </button>
        <button type="button" className={recording ? 'composer__voice composer__voice--on' : 'composer__voice'} disabled={streaming}
          aria-pressed={recording} onPointerDown={startVoice} onPointerUp={stopVoice} onPointerLeave={stopVoice}
          onKeyDown={e => { if ((e.key === ' ' || e.key === 'Enter') && !e.repeat) { e.preventDefault(); void startVoice() } }}
          onKeyUp={e => { if (e.key === ' ' || e.key === 'Enter') stopVoice() }}>
          <Mic aria-hidden="true" strokeWidth={2} /><span>{t('chat.voice')}</span>
        </button>
        {streaming ? (
          <button type="button" className="composer__send composer__send--stop" onClick={onStop}>
            <Square aria-hidden="true" strokeWidth={2} /><span>{t('chat.stop')}</span>
          </button>
        ) : (
          <button type="submit" className="composer__send" disabled={!canSend} aria-disabled={!canSend}>
            <Send aria-hidden="true" strokeWidth={2} /><span>{t('chat.send')}</span>
          </button>
        )}
      </div>
    </form>
  )
}
