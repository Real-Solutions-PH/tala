import { ArrowDown, ArrowUp } from 'lucide-react'
import { Badge } from '../../../components/Badge'
import { formatDate, useLang, useT } from '../../../i18n'
import type { Of } from './types'

export function LabTableBlock({ block }: { block: Of<'lab_table'> }) {
  const t = useT()
  const [lang] = useLang()
  return (
    <section className="cblock">
      <h3 className="cblock__title">{t('blocks.labsTitle')}</h3>
      <ul className="cblock__list cblock__list--plain">
        {block.rows.map((r, i) => (
          <li key={i}>
            <div>
              <div className="cblock__row">
                <span className="cblock__strong">{r.label}</span>
                {r.flag === 'high' && <Badge tone="warn" icon={ArrowUp}>{t('blocks.high')}</Badge>}
                {r.flag === 'low' && <Badge tone="warn" icon={ArrowDown}>{t('blocks.low')}</Badge>}
              </div>
              <p className="cblock__value">{r.value}{r.unit ? ` ${r.unit}` : ''}</p>
              <p className="cblock__muted">
                {r.date ? formatDate(r.date, lang) : ''}{r.ref ? ` · ${t('blocks.refRange', { range: r.ref })}` : ''}
              </p>
            </div>
          </li>
        ))}
      </ul>
    </section>
  )
}
