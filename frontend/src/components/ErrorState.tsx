import { RotateCcw, TriangleAlert } from 'lucide-react'
import { useT, type Key } from '../i18n'
import { Button } from './Button'

/** Shown when loading failed. Says what happened in plain words and offers Retry. */
export function ErrorState({ onRetry, message = 'errors.generic' }: { onRetry: () => void; message?: Key }) {
  const t = useT()
  return (
    <div className="state state--error" role="alert">
      <span className="state__icon" aria-hidden="true"><TriangleAlert strokeWidth={2} /></span>
      <h2 className="state__title">{t('errors.title')}</h2>
      <p className="state__body">{t(message)}</p>
      <Button size="lg" variant="secondary" icon={RotateCcw} onClick={onRetry}>{t('common.retry')}</Button>
    </div>
  )
}
