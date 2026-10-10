import { Link } from 'react-router'
import { WalletCards } from 'lucide-react'
import { useT } from '../../../i18n'
import type { Of } from './types'

export function CardBlock({ block }: { block: Of<'card'> }) {
  const t = useT()
  return (
    <section className="cblock cblock--card">
      <img className="cblock__card-img" src={block.front_url} alt={block.label} />
      <Link className="btn btn--secondary btn--block" to={`/cards/${block.card_id}`}>
        <WalletCards aria-hidden="true" strokeWidth={2} /><span>{t('blocks.showCard')}</span>
      </Link>
    </section>
  )
}
