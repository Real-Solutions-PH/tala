import { COMPANION, EYES, LENS, PERSON, VIEWBOX } from './geometry'

export type MarkState = 'idle' | 'listening' | 'thinking' | 'speaking'

type Props = {
  size?: number
  /** With eyes the large circle becomes Usap, the talking character. */
  eyes?: boolean
  state?: MarkState
  /** Accessible name; omit when a visible word ("Kapiling") sits next to the mark. */
  title?: string
  className?: string
}

/** The two-circle Kapiling mark, drawn inline so it follows the theme tokens. */
export function Mark({ size = 32, eyes = false, state = 'idle', title, className }: Props) {
  const cls = ['mark', eyes && `mark--${state}`, className].filter(Boolean).join(' ')
  return (
    <svg className={cls} width={size} height={size} viewBox={VIEWBOX} role={title ? 'img' : undefined}
      aria-label={title} aria-hidden={title ? undefined : true} focusable="false">
      <g className="mark__person">
        <circle {...PERSON} fill="var(--primary)" />
        {eyes && (
          <g className="mark__eyes" fill="var(--on-primary)">
            {EYES.map((e, i) => <circle key={i} {...e} />)}
          </g>
        )}
      </g>
      <circle {...COMPANION} fill="var(--primary)" />
      <path d={LENS} fill="var(--gold)" />
    </svg>
  )
}
