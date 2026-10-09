import type { ReactNode } from 'react'
import type { LucideIcon } from 'lucide-react'

/** Status word on a soft tint. Always carries a word (and ideally an icon), never colour alone. */
export function Badge({ tone, icon: Icon, children }: { tone: 'ok' | 'warn' | 'danger' | 'info'; icon?: LucideIcon; children: ReactNode }) {
  return (
    <span className={`badge badge--${tone}`}>
      {Icon && <Icon aria-hidden="true" strokeWidth={2.25} />}
      {children}
    </span>
  )
}
