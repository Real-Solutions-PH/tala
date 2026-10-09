import type { LucideIcon } from 'lucide-react'
import { Button } from './Button'

type Props = {
  icon: LucideIcon
  title: string
  body: string
  action?: { label: string; onClick: () => void; icon?: LucideIcon }
}

/** Shown when a list has nothing yet. Always offers the next step when there is one. */
export function EmptyState({ icon: Icon, title, body, action }: Props) {
  return (
    <div className="state">
      <span className="state__icon" aria-hidden="true"><Icon strokeWidth={2} /></span>
      <h2 className="state__title">{title}</h2>
      <p className="state__body">{body}</p>
      {action && <Button size="lg" icon={action.icon} onClick={action.onClick}>{action.label}</Button>}
    </div>
  )
}
