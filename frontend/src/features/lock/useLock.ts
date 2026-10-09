// Which profile is unlocked in this browser. The session itself is an httpOnly cookie the app cannot read,
// so we remember the profile id (React state + localStorage) and let any 401 from the API clear it.
import { createContext, createElement, useCallback, useContext, useMemo, useState, type ReactNode } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { api } from '../../api/client'

export const PROFILE_KEY = 'kapiling.profile'

function readStored(): number | null {
  try {
    const n = Number(localStorage.getItem(PROFILE_KEY))
    return Number.isInteger(n) && n > 0 ? n : null
  } catch {
    return null // storage blocked: the user simply unlocks again
  }
}

function writeStored(pid: number | null): void {
  try {
    if (pid == null) localStorage.removeItem(PROFILE_KEY)
    else localStorage.setItem(PROFILE_KEY, String(pid))
  } catch { /* not persisted; still works for this tab */ }
}

type LockCtx = {
  profileId: number | null
  /** POST /unlock. Rejects with ApiError (401 wrong PIN, 429 backed off) and stays on the lock screen. */
  unlock: (profileId: number, pin: string) => Promise<void>
  /** POST /lock, then forget the profile. */
  lock: () => Promise<void>
  /** Forget the profile without calling the server (the session already ended, e.g. after a 401). */
  forget: () => void
}

const Ctx = createContext<LockCtx | null>(null)

export function LockProvider({ children }: { children: ReactNode }) {
  const [profileId, setProfileId] = useState<number | null>(readStored)
  const qc = useQueryClient()

  const set = useCallback((pid: number | null) => {
    setProfileId(pid)
    writeStored(pid)
  }, [])

  const forget = useCallback(() => {
    set(null)
    qc.removeQueries({ predicate: q => q.queryKey[0] !== 'profiles' }) // nobody else sees the last person's records
  }, [qc, set])

  const unlock = useCallback(async (pid: number, pin: string) => {
    await api.send('POST', '/unlock', { profile_id: pid, pin })
    qc.removeQueries({ predicate: q => q.queryKey[0] !== 'profiles' })
    set(pid)
  }, [qc, set])

  const lock = useCallback(async () => {
    try { await api.send('POST', '/lock') } finally { forget() }
  }, [forget])

  const value = useMemo(() => ({ profileId, unlock, lock, forget }), [profileId, unlock, lock, forget])
  return createElement(Ctx.Provider, { value }, children)
}

export function useLock(): LockCtx {
  const ctx = useContext(Ctx)
  if (!ctx) throw new Error('useLock must be used inside <LockProvider>')
  return ctx
}
