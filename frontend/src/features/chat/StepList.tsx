import { Check, ChevronRight } from 'lucide-react'
import { useT, type Key } from '../../i18n'

export type Step = { name: string; done: boolean }

/** Live rows while streaming (spinner, then a check); afterwards one "3 hakbang" disclosure. */
export function StepList({ steps, live }: { steps: Step[]; live: boolean }) {
  const t = useT()
  if (!steps.length) return null
  const label = (n: string) => t(`steps.${n}` as Key)
  const rows = (
    <ul className="steps">
      {steps.map(s => (
        <li key={s.name} className={s.done ? 'step step--done' : 'step'}>
          {s.done ? <Check aria-hidden="true" className="step__icon" /> : <span className="spinner step__icon" aria-hidden="true" />}
          <span>{label(s.name)}</span>
        </li>
      ))}
    </ul>
  )
  if (live) {
    const current = [...steps].reverse().find(s => !s.done) ?? steps[steps.length - 1]
    return (
      <div className="steps-live">
        {rows}
        {/* One announcement per step change: the text only changes when the current step does. */}
        <p className="sr-only" aria-live="polite">{label(current.name)}</p>
      </div>
    )
  }
  return (
    <details className="steps-done">
      <summary><ChevronRight aria-hidden="true" className="steps-done__chev" />{t('chat.stepsDone', { n: steps.length })}</summary>
      {rows}
    </details>
  )
}
