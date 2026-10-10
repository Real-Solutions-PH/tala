// Today's doses: the shapes, time helpers and the shared "mark as taken" action.
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../../api/client'
import { keys } from '../../api/queries'
import type { Med, MedsDay } from '../../api/types'
import { useToast } from '../../components/Toast'
import { formatDate, useT, type Lang } from '../../i18n'
import { errorKey } from '../lock/errorKey'

export type Dose = MedsDay['today'][number] & { name?: string; strength?: string | null }
export type Period = 'morning' | 'noon' | 'night'

export const REFILL_AT = 7

/** Local calendar date, YYYY-MM-DD (not UTC: 7 a.m. in Manila is still "today"). */
export function localDate(d = new Date()): string {
  const p = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`
}

/** Slots are "HH:MM" times from the schedule (or a named period). Before 11 is morning, before 16 noon. */
export function periodOf(slot: string): Period {
  if (slot === 'morning' || slot === 'noon' || slot === 'night') return slot
  const h = Number(slot.split(':')[0])
  if (!Number.isFinite(h)) return 'morning'
  return h < 11 ? 'morning' : h < 16 ? 'noon' : 'night'
}

/** The backend sends `schedule` as JSON text (a raw DB column), while the plan says string[]: accept both. */
export function scheduleOf(m: Med): string[] {
  const v: unknown = m.schedule
  if (Array.isArray(v)) return v.map(String)
  if (typeof v === 'string') {
    try {
      const parsed: unknown = JSON.parse(v)
      return Array.isArray(parsed) ? parsed.map(String) : []
    } catch { return v ? [v] : [] }
  }
  return []
}

export function slotTime(slot: string, lang: Lang): string {
  const m = slot.match(/^(\d{1,2}):(\d{2})$/)
  if (!m) return slot
  return formatDate(new Date(2000, 0, 1, Number(m[1]), Number(m[2])), lang, { hour: 'numeric', minute: '2-digit' })
}

/** Mark a dose taken or not, optimistically, with a toast either way. Shared by Gamot and Home. */
export function useToggleDose(profileId: number | null, date: string, meds: MedsDay | undefined) {
  const t = useT()
  const toast = useToast()
  const qc = useQueryClient()
  const key = keys.meds(profileId, date)
  const toggle = useMutation({
    mutationFn: ({ dose, take }: { dose: Dose; take: boolean }) =>
      api.send(take ? 'POST' : 'DELETE', `/profiles/${profileId}/meds/${dose.med_id}/taken`, { date, slot: dose.slot }),
    onMutate: async ({ dose, take }) => {
      await qc.cancelQueries({ queryKey: key })
      const before = qc.getQueryData<MedsDay>(key)
      qc.setQueryData<MedsDay>(key, d => d && {
        ...d,
        today: d.today.map(x => x.med_id === dose.med_id && x.slot === dose.slot
          ? { ...x, taken_at: take ? new Date().toISOString() : null } : x),
      })
      return { before }
    },
    onSuccess: (_r, { dose, take }) => {
      const name = dose.name ?? meds?.meds.find(m => m.id === dose.med_id)?.name ?? ''
      toast(take ? t('toasts.medTaken', { name }) : t('meds.untaken', { name }))
    },
    onError: (err, _v, ctx) => {
      if (ctx?.before) qc.setQueryData(key, ctx.before)
      toast(t(errorKey(err, 'toasts.failed')), 'error')
    },
    onSettled: () => qc.invalidateQueries({ queryKey: key }),
  })

  return (dose: Dose) => toggle.mutate({ dose, take: dose.taken_at == null })
}
