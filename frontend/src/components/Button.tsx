import type { ButtonHTMLAttributes, ReactNode } from 'react'
import type { LucideIcon } from 'lucide-react'

export type ButtonProps = Omit<ButtonHTMLAttributes<HTMLButtonElement>, 'children'> & {
  variant?: 'primary' | 'secondary' | 'danger' | 'ghost'
  size?: 'md' | 'lg'
  icon?: LucideIcon
  loading?: boolean
  block?: boolean
  children: ReactNode
}

/** Labelled button. md is at least 48px tall, lg at least 64px. While loading it is disabled and aria-busy. */
export function Button({ variant = 'primary', size = 'md', icon: Icon, loading = false, block = false,
  className, children, disabled, type = 'button', ...rest }: ButtonProps) {
  const cls = ['btn', `btn--${variant}`, size === 'lg' && 'btn--lg', block && 'btn--block', className].filter(Boolean).join(' ')
  return (
    <button {...rest} type={type} className={cls} disabled={disabled || loading} aria-busy={loading || undefined}>
      {loading ? <span className="spinner" aria-hidden="true" /> : Icon && <Icon aria-hidden="true" strokeWidth={2} />}
      <span>{children}</span>
    </button>
  )
}
