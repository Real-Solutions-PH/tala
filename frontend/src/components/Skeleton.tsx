import type { CSSProperties } from 'react'

/** Loading placeholder block. The shimmer is off under prefers-reduced-motion. */
export function Skeleton({ width = '100%', height = 20, radius, className }: {
  width?: CSSProperties['width']; height?: CSSProperties['height']; radius?: CSSProperties['borderRadius']; className?: string
}) {
  return <span aria-hidden="true" className={['skeleton', className].filter(Boolean).join(' ')} style={{ width, height, borderRadius: radius }} />
}
