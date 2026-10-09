import type { ButtonHTMLAttributes, ReactNode } from 'react'
import type { LucideIcon } from 'lucide-react'

type Props = Omit<ButtonHTMLAttributes<HTMLButtonElement>, 'children'> & {
  icon?: LucideIcon
  /** Toggle chips pass `selected`; selected chips are gold with ink text. */
  selected?: boolean
  children: ReactNode
}

/** Quick-action or filter chip, 48px tall. */
export function Chip({ icon: Icon, selected, className, children, type = 'button', ...rest }: Props) {
  return (
    <button {...rest} type={type} className={['chip', className].filter(Boolean).join(' ')}
      aria-pressed={selected === undefined ? undefined : selected}>
      {Icon && <Icon aria-hidden="true" strokeWidth={2} />}
      <span>{children}</span>
    </button>
  )
}
