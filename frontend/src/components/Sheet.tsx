import { useEffect, useId, useRef, type ReactNode } from 'react'
import { X } from 'lucide-react'
import { useT } from '../i18n'
import { Button } from './Button'

type Props = { open: boolean; onClose: () => void; title: string; children: ReactNode }

/** Bottom sheet built on the native modal <dialog>: focus is trapped and Escape closes it. */
export function Sheet({ open, onClose, title, children }: Props) {
  const ref = useRef<HTMLDialogElement>(null)
  const titleId = useId()
  const t = useT()

  useEffect(() => {
    const d = ref.current
    if (!d) return
    if (open && !d.open) d.showModal?.()
    if (!open && d.open) d.close?.()
  }, [open])

  return (
    <dialog ref={ref} className="sheet" aria-labelledby={titleId} onClose={onClose}
      onClick={e => { if (e.target === ref.current) onClose() }}>
      <div className="sheet__head">
        <h2 id={titleId} className="sheet__title">{title}</h2>
        <Button variant="ghost" icon={X} onClick={onClose}>{t('common.close')}</Button>
      </div>
      <div className="sheet__body">{children}</div>
    </dialog>
  )
}
