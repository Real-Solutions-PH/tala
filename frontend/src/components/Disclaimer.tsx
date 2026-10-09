import { Info } from 'lucide-react'
import { useT } from '../i18n'

/** The fixed safety reminder (spec §2). Text always comes from the catalogue, never from the model. */
export function Disclaimer() {
  const t = useT()
  return (
    <aside className="disclaimer" aria-label={t('safety.disclaimerTitle')}>
      <Info aria-hidden="true" strokeWidth={2.25} />
      <p>{t('safety.disclaimer')}</p>
    </aside>
  )
}
