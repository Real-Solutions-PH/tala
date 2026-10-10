import { useT, type Key } from '../../../i18n'
import type { Of } from './types'

export function ProfileFieldsBlock({ block }: { block: Of<'profile_fields'> }) {
  const t = useT()
  return (
    <section className="cblock">
      <h3 className="cblock__title">{t('blocks.profileTitle')}</h3>
      <dl className="cblock__fields">
        {block.fields.map(f => (
          <div key={f.key}><dt>{t(f.key as Key)}</dt><dd>{f.value}</dd></div>
        ))}
      </dl>
    </section>
  )
}
