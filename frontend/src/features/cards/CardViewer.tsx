// Full-screen card viewer for showing a card to the nurse: black background, the screen kept awake,
// a front/back toggle, pinch to zoom, and a labelled Close button (Escape closes too).
import { useEffect, useRef, useState, type PointerEvent as ReactPointerEvent } from 'react'
import { Sun, X } from 'lucide-react'
import type { WalletCard } from '../../api/types'
import { useT } from '../../i18n'
import './cards.css'

type Side = 'front' | 'back'
type WakeLockLike = { release: () => Promise<void> }
type WakeNavigator = Navigator & { wakeLock?: { request: (type: 'screen') => Promise<WakeLockLike> } }

/** Keeps the screen on while mounted, where the browser supports the Screen Wake Lock API. */
function useWakeLock() {
  useEffect(() => {
    const wl = (navigator as WakeNavigator).wakeLock
    if (!wl) return
    let lock: WakeLockLike | null = null
    let gone = false
    const request = () => wl.request('screen').then(l => {
      if (gone) void l.release().catch(() => {})
      else lock = l
    }).catch(() => { /* denied or hidden tab: the card still shows */ })
    void request()
    // The browser drops the lock when the tab is hidden; ask again when it comes back.
    const onVisible = () => { if (document.visibilityState === 'visible' && !gone) void request() }
    document.addEventListener('visibilitychange', onVisible)
    return () => {
      gone = true
      document.removeEventListener('visibilitychange', onVisible)
      void lock?.release().catch(() => {})
    }
  }, [])
}

const MAX_ZOOM = 4

/** Two-finger pinch to zoom and one-finger pan while zoomed. Double-tap toggles 2x. */
function usePinchZoom() {
  const [view, setView] = useState({ scale: 1, x: 0, y: 0 })
  const pts = useRef(new Map<number, { x: number; y: number }>())
  const start = useRef<{ dist: number; scale: number; x: number; y: number; px: number; py: number } | null>(null)

  const dist = () => {
    const [a, b] = [...pts.current.values()]
    return Math.hypot(a.x - b.x, a.y - b.y)
  }

  const onPointerDown = (e: ReactPointerEvent) => {
    e.currentTarget.setPointerCapture?.(e.pointerId)
    pts.current.set(e.pointerId, { x: e.clientX, y: e.clientY })
    start.current = { dist: pts.current.size === 2 ? dist() : 0, scale: view.scale, x: view.x, y: view.y, px: e.clientX, py: e.clientY }
  }
  const onPointerMove = (e: ReactPointerEvent) => {
    if (!pts.current.has(e.pointerId) || !start.current) return
    pts.current.set(e.pointerId, { x: e.clientX, y: e.clientY })
    const s = start.current
    if (pts.current.size === 2 && s.dist > 0) {
      const scale = Math.min(MAX_ZOOM, Math.max(1, s.scale * (dist() / s.dist)))
      setView(v => ({ ...v, scale, ...(scale === 1 ? { x: 0, y: 0 } : {}) }))
    } else if (pts.current.size === 1 && view.scale > 1) {
      setView(v => ({ ...v, x: s.x + (e.clientX - s.px), y: s.y + (e.clientY - s.py) }))
    }
  }
  const onPointerUp = (e: ReactPointerEvent) => {
    pts.current.delete(e.pointerId)
    start.current = pts.current.size === 1
      ? (() => { const [p] = [...pts.current.values()]; return { dist: 0, scale: view.scale, x: view.x, y: view.y, px: p.x, py: p.y } })()
      : null
  }
  const onDoubleClick = () => setView(v => (v.scale > 1 ? { scale: 1, x: 0, y: 0 } : { scale: 2, x: 0, y: 0 }))

  return {
    style: { transform: `translate(${view.x}px, ${view.y}px) scale(${view.scale})` },
    handlers: { onPointerDown, onPointerMove, onPointerUp, onPointerCancel: onPointerUp, onDoubleClick },
  }
}

/** Remounted per side (key), so turning the card over resets the zoom. */
function ZoomImage({ src, alt }: { src: string; alt: string }) {
  const zoom = usePinchZoom()
  return (
    <div className="viewer__stage" {...zoom.handlers}>
      <img className="viewer__img" src={src} alt={alt} draggable={false} style={zoom.style} />
    </div>
  )
}

export function CardViewer({ card, onClose }: { card: WalletCard; onClose: () => void }) {
  const t = useT()
  const [side, setSide] = useState<Side>('front')
  const closeRef = useRef<HTMLButtonElement>(null)
  const rootRef = useRef<HTMLDivElement>(null)
  useWakeLock()

  useEffect(() => {
    closeRef.current?.focus()
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') { e.preventDefault(); onClose(); return }
      if (e.key !== 'Tab' || !rootRef.current) return
      // Focus trap: Tab cycles through the viewer's own controls, never the page behind it.
      const items = [...rootRef.current.querySelectorAll<HTMLElement>('button:not([disabled]), [href], [tabindex]:not([tabindex="-1"])')]
      if (items.length === 0) return
      const first = items[0], last = items[items.length - 1]
      const inside = rootRef.current.contains(document.activeElement)
      if (e.shiftKey && (document.activeElement === first || !inside)) { e.preventDefault(); last.focus() }
      else if (!e.shiftKey && (document.activeElement === last || !inside)) { e.preventDefault(); first.focus() }
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [onClose])

  const src = side === 'back' && card.back_url ? card.back_url : card.front_url
  const sideLabel = t(side === 'front' ? 'cards.front' : 'cards.back')

  return (
    <div ref={rootRef} className="viewer viewer--bright" role="dialog" aria-modal="true" aria-labelledby="viewer-title">
      <div className="viewer__bar">
        <h1 id="viewer-title" className="viewer__title">{card.label}</h1>
        <button ref={closeRef} type="button" className="viewer__close" onClick={onClose}>
          <X aria-hidden="true" strokeWidth={2.25} />
          <span className="sr-only">{t('common.close')}</span>
        </button>
      </div>

      <ZoomImage key={side} src={src} alt={`${card.label}, ${sideLabel}`} />

      <div className="viewer__foot">
        {card.number_masked && <p className="viewer__number tabular">{card.number_masked}</p>}
        {card.back_url && (
          <div className="viewer__sides" role="group" aria-label={t('cards.flip')}>
            {(['front', 'back'] as const).map(s => (
              <button key={s} type="button" className="viewer__side" aria-pressed={side === s} onClick={() => setSide(s)}>
                {t(s === 'front' ? 'cards.front' : 'cards.back')}
              </button>
            ))}
          </div>
        )}
        <p className="viewer__bright"><Sun aria-hidden="true" strokeWidth={2} />{t('cards.brightNote')}</p>
      </div>
    </div>
  )
}
