import { Pill } from 'lucide-react'
import { useT } from '../../../i18n'
import type { Of } from './types'

export function MedListBlock({ block }: { block: Of<'med_list'> }) {
  const t = useT()
  return (
    <section className="cblock">
      <h3 className="cblock__title">{t('blocks.medsTitle')}</h3>
      <ul className="cblock__list">
        {block.meds.map((m, i) => (
          <li key={i}>
            <Pill aria-hidden="true" strokeWidth={2} className="cblock__icon" />
            <div>
              <p className="cblock__strong">{m.name}{m.strength ? ` ${m.strength}` : ''}</p>
              {m.schedule.length > 0 && <p className="cblock__muted">{m.schedule.join(' · ')}</p>}
              {m.purpose && <p className="cblock__muted">{m.purpose}</p>}
            </div>
          </li>
        ))}
      </ul>
    </section>
  )
}
