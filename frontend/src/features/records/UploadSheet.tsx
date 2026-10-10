import type { ChangeEvent } from 'react'
import { useNavigate } from 'react-router'
import { Camera, ImagePlus } from 'lucide-react'
import { Sheet } from '../../components/Sheet'
import { useToast } from '../../components/Toast'
import { useT } from '../../i18n'
import { useLock } from '../lock/useLock'
import { useUploadDocument } from './api'
import './records.css'

const MAX_BYTES = 20 * 1024 * 1024
const okType = (f: File) => f.type.startsWith('image/') || f.type === 'application/pdf'

/** "Magdagdag ng resulta": take a photo with the camera, or choose a photo or PDF. Then open its page. */
export function UploadSheet({ open, onClose }: { open: boolean; onClose: () => void }) {
  const t = useT()
  const toast = useToast()
  const navigate = useNavigate()
  const { profileId } = useLock()
  const upload = useUploadDocument(profileId)

  const onPick = (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    e.target.value = '' // the same file can be chosen again after an error
    if (!file) return
    if (!okType(file)) { toast(t('errors.fileType'), 'error'); return }
    if (file.size > MAX_BYTES) { toast(t('errors.fileTooBig'), 'error'); return }
    upload.mutate(file, {
      onSuccess: doc => {
        toast(t('toasts.recordAdded'))
        onClose()
        navigate(`/records/documents/${doc.id}`)
      },
      onError: () => toast(t('toasts.failed'), 'error'),
    })
  }

  const busy = upload.isPending
  return (
    <Sheet open={open} onClose={onClose} title={t('records.addResult')}>
      <div className="upload">
        <p className="muted">{t('records.uploadHelp')}</p>
        <label className={`btn btn--primary btn--lg btn--block upload__pick${busy ? ' is-busy' : ''}`} aria-busy={busy || undefined}>
          {busy ? <span className="spinner" aria-hidden="true" /> : <Camera aria-hidden="true" strokeWidth={2} />}
          <span>{busy ? t('records.saving') : t('common.takePhoto')}</span>
          <input className="sr-only" type="file" accept="image/*" capture="environment" onChange={onPick} disabled={busy} />
        </label>
        <label className={`btn btn--secondary btn--lg btn--block upload__pick${busy ? ' is-busy' : ''}`}>
          <ImagePlus aria-hidden="true" strokeWidth={2} />
          <span>{t('records.chooseFile')}</span>
          <input className="sr-only" type="file" accept="image/*,application/pdf" onChange={onPick} disabled={busy} />
        </label>
      </div>
    </Sheet>
  )
}
