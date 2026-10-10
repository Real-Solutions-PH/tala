import { Sheet } from '../../components/Sheet'
import { Button } from '../../components/Button'
import { useT } from '../../i18n'
import { Trash2 } from 'lucide-react'

type Props = {
  open: boolean; title: string; body: string; confirmLabel: string
  busy?: boolean; onConfirm: () => void; onClose: () => void
}

/** Asks before anything is removed. The safe choice (cancel) comes second and is never red. */
export function ConfirmSheet({ open, title, body, confirmLabel, busy, onConfirm, onClose }: Props) {
  const t = useT()
  return (
    <Sheet open={open} onClose={onClose} title={title}>
      <div className="confirm">
        <p>{body}</p>
        <div className="confirm__actions">
          <Button variant="danger" size="lg" block icon={Trash2} loading={busy} onClick={onConfirm}>{confirmLabel}</Button>
          <Button variant="secondary" size="lg" block onClick={onClose}>{t('common.cancel')}</Button>
        </div>
      </div>
    </Sheet>
  )
}
