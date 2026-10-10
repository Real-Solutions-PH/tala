import { Copy } from 'lucide-react'
import { Button } from '../../../components/Button'
import { useToast } from '../../../components/Toast'
import { useT } from '../../../i18n'
import type { Of } from './types'

export function FormAnswersBlock({ block }: { block: Of<'form_answers'> }) {
  const t = useT()
  const toast = useToast()
  const copy = async () => {
    const text = block.items.map(i => `${i.field}: ${i.answer ?? t('blocks.notAnswered')}`).join('\n')
    try { await navigator.clipboard.writeText(text); toast(t('blocks.copied')) } catch { toast(t('chat.sendFailed'), 'error') }
  }
  return (
    <section className="cblock">
      <h3 className="cblock__title">{t('blocks.formTitle')}</h3>
      <dl className="cblock__fields">
        {block.items.map((i, n) => (
          <div key={n}>
            <dt>{i.field}</dt>
            <dd className={i.answer == null ? 'cblock__missing' : undefined}>{i.answer ?? t('blocks.notAnswered')}</dd>
          </div>
        ))}
      </dl>
      <Button variant="secondary" icon={Copy} onClick={copy}>{t('blocks.copyAnswers')}</Button>
    </section>
  )
}
