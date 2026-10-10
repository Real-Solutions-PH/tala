import { ShieldAlert } from 'lucide-react'
import { useT } from '../../../i18n'
import type { Of } from './types'

/** The text is always the catalogue's safety.refusal.*, never the model's. */
export function RefusalBlock({ block }: { block: Of<'refusal'> }) {
  const t = useT()
  const kind = block.kind === 'medication' ? 'medication' : 'diagnosis'
  return (
    <aside className="cblock cblock--refusal" role="note">
      <ShieldAlert aria-hidden="true" strokeWidth={2.25} />
      <p>{t(`safety.refusal.${kind}`)}</p>
    </aside>
  )
}
