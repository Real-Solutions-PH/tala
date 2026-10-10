// Building blocks shared by Settings and Profile: a titled card section, a labelled field, a form error.
import { useId, type ReactNode } from 'react'
import { CircleAlert, type LucideIcon } from 'lucide-react'

/** A section as in the prototype's settings sheet: a plain title over one white panel. `icon` is kept for callers. */
export function Section({ title, hint, children }: { icon?: LucideIcon; title: string; hint?: string; children: ReactNode }) {
  const id = useId()
  return (
    <section className="sec settings-section" aria-labelledby={id}>
      <h2 id={id} className="settings-section__head">{title}</h2>
      <div className="panel settings-section__panel">
        {hint && <p className="settings-section__hint">{hint}</p>}
        {children}
      </div>
    </section>
  )
}

export function Field({ label, hint, error, children }: { label: string; hint?: string; error?: string | null; children: (ids: { id: string; describedBy?: string }) => ReactNode }) {
  const id = useId()
  const hintId = hint ? `${id}-hint` : undefined
  const errId = error ? `${id}-err` : undefined
  const describedBy = [hintId, errId].filter(Boolean).join(' ') || undefined
  return (
    <div className="field">
      <label className="field__label" htmlFor={id}>{label}</label>
      {hint && <span className="field__hint" id={hintId}>{hint}</span>}
      {children({ id, describedBy })}
      {error && <span className="field__error" id={errId}>{error}</span>}
    </div>
  )
}

export function FormError({ message }: { message: string | null }) {
  if (!message) return null
  return <p className="form-error" role="alert"><CircleAlert aria-hidden="true" /><span>{message}</span></p>
}
