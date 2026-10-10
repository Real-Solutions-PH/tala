// The text-size setting (DESIGN.md principle 1): 100 / 125 / 150%, applied as --text-scale on <html> so every
// size token scales. Remembered per device in localStorage and re-applied when the app starts.
import { useLayoutEffect } from 'react'

export const TEXT_SCALE_KEY = 'kapiling.textScale'
export const SCALES = [1, 1.25, 1.5] as const
export type Scale = (typeof SCALES)[number]

export function readTextScale(): Scale {
  try {
    const n = Number(localStorage.getItem(TEXT_SCALE_KEY))
    return (SCALES as readonly number[]).includes(n) ? (n as Scale) : 1
  } catch {
    return 1 // storage blocked: normal size
  }
}

function setVar(scale: Scale): void {
  document.documentElement.style.setProperty('--text-scale', String(scale))
}

/** Apply now and remember for next time. */
export function applyTextScale(scale: Scale): void {
  setVar(scale)
  try { localStorage.setItem(TEXT_SCALE_KEY, String(scale)) } catch { /* not remembered; still applied */ }
}

/** Mounted once at the app root: re-applies the remembered size before the first paint. */
export function useStoredTextScale(): void {
  useLayoutEffect(() => { setVar(readTextScale()) }, [])
}
