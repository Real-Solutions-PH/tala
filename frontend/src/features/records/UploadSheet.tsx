import { useEffect, useState, type ChangeEvent } from 'react'
import { useNavigate } from 'react-router'
import { Check, ImagePlus, X } from 'lucide-react'
import { useToast } from '../../components/Toast'
import { useT, type Key } from '../../i18n'
import { useLock } from '../lock/useLock'
import { useUploadDocument } from './api'
import './records.css'

const MAX_BYTES = 20 * 1024 * 1024
const okType = (f: File) => f.type.startsWith('image/') || f.type === 'application/pdf'
const STEPS: Key[] = ['records.reading1', 'records.reading2', 'records.reading3']

/**
 * "Scan a record", after the prototype: a dark camera screen with a page frame and a round shutter (the phone's
 * own camera), or a photo or PDF from the phone. While the file is sent and read, "Reading on this phone" ticks
 * through its steps; then the document opens, where the values wait to be confirmed.
 */
export function UploadSheet({ open, onClose }: { open: boolean; onClose: () => void }) {
  const t = useT()
  const toast = useToast()
  const navigate = useNavigate()
  const { profileId } = useLock()
  const upload = useUploadDocument(profileId)
  const [step, setStep] = useState(0)
  const busy = upload.isPending

  // The last step keeps spinning until the server answers; the earlier ones tick on a short clock.
  useEffect(() => {
    if (!busy) return
    const id = setInterval(() => setStep(s => Math.min(s + 1, STEPS.length - 1)), 750)
    return () => clearInterval(id)
  }, [busy])

  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape' && !busy) onClose() }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [open, busy, onClose])

  if (!open) return null

  const onPick = (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    e.target.value = '' // the same file can be chosen again after an error
    if (!file) return
    if (!okType(file)) { toast(t('errors.fileType'), 'error'); return }
    if (file.size > MAX_BYTES) { toast(t('errors.fileTooBig'), 'error'); return }
    setStep(0)
    upload.mutate(file, {
      onSuccess: doc => {
        toast(t('toasts.recordAdded'))
        onClose()
        navigate(`/records/documents/${doc.id}`)
      },
      onError: () => toast(t('toasts.failed'), 'error'),
    })
  }

  if (busy) {
    return (
      <div className="ov" role="dialog" aria-modal="true" aria-labelledby="reading-title">
        <div className="ov-top"><h2 id="reading-title">{t('records.readingTitle')}</h2></div>
        <div className="ov-body">
          <ol className="panel steps reading" aria-live="polite">
            {STEPS.slice(0, step + 1).map((k, i) => (
              <li key={k}>{i < step ? <span className="check"><Check aria-hidden="true" strokeWidth={3} /></span> : <span className="spin" aria-hidden="true" />}{t(k)}</li>
            ))}
          </ol>
        </div>
      </div>
    )
  }

  return (
    <div className="ov ov--cam" role="dialog" aria-modal="true" aria-labelledby="scan-title">
      <div className="ov-top">
        <button type="button" className="iconbtn iconbtn--cam" onClick={onClose}>
          <X aria-hidden="true" strokeWidth={2} /><span className="sr-only">{t('common.close')}</span>
        </button>
        <h2 id="scan-title">{t('records.scan')}</h2>
      </div>
      <div className="cam">
        <p className="camhint">{t('records.camHint')}</p>
        <div className="frame" aria-hidden="true" />
      </div>
      <div className="shutter">
        <label className="pickfile">
          <ImagePlus aria-hidden="true" strokeWidth={2} /><span>{t('records.chooseFile')}</span>
          <input className="sr-only" type="file" accept="image/*,application/pdf" onChange={onPick} />
        </label>
        <label className="shutter__btn">
          <span className="sr-only">{t('common.takePhoto')}</span>
          <input className="sr-only" type="file" accept="image/*" capture="environment" onChange={onPick} />
        </label>
      </div>
    </div>
  )
}
