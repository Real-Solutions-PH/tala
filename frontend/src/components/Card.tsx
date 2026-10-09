import type { HTMLAttributes, ReactNode } from 'react'

type Props = HTMLAttributes<HTMLElement> & { as?: 'section' | 'article' | 'div' | 'li'; flat?: boolean; children: ReactNode }

/** Flat surface on the paper ground: 20px radius, one soft shadow. */
export function Card({ as: Tag = 'div', flat = false, className, children, ...rest }: Props) {
  return <Tag {...rest} className={['card', flat && 'card--flat', className].filter(Boolean).join(' ')}>{children}</Tag>
}
