import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from 'react'
import { CircleAlert, CircleCheck } from 'lucide-react'

export const TOAST_MS = 4000

type Tone = 'ok' | 'error'
type Toast = { id: number; message: string; tone: Tone }
type ShowToast = (message: string, tone?: Tone) => void

const ToastContext = createContext<ShowToast | null>(null)

/** Reports the outcome of every user action (G-C-079). Polite live region; each toast leaves after 4 s. */
export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([])
  const nextId = useRef(1)
  const timers = useRef(new Set<ReturnType<typeof setTimeout>>())

  const show = useCallback<ShowToast>((message, tone = 'ok') => {
    const id = nextId.current++
    setToasts(ts => [...ts.slice(-2), { id, message, tone }])
    const timer = setTimeout(() => {
      timers.current.delete(timer)
      setToasts(ts => ts.filter(x => x.id !== id))
    }, TOAST_MS)
    timers.current.add(timer)
  }, [])

  useEffect(() => {
    const all = timers.current
    return () => { all.forEach(clearTimeout); all.clear() }
  }, [])

  return (
    <ToastContext.Provider value={show}>
      {children}
      <div className="toasts" aria-live="polite" role="status">
        {toasts.map(x => (
          <div key={x.id} className="toast">
            {x.tone === 'error' ? <CircleAlert aria-hidden="true" /> : <CircleCheck aria-hidden="true" />}
            <span>{x.message}</span>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  )
}

export function useToast(): ShowToast {
  const ctx = useContext(ToastContext)
  if (!ctx) throw new Error('useToast must be used inside <ToastProvider>')
  return ctx
}
