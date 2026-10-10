// Medicines: today's doses grouped Umaga / Tanghali / Gabi with an optimistic "Markahang nainom" action
// that turns into the "Nainom na" status (tap again to undo),
// refill warnings, and the full list with purpose and prescriber.
import { useMemo } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Check, PackageOpen, Pill, Stethoscope, Sun, Sunrise, Moon, type LucideIcon } from 'lucide-react'
import { api } from '../../api/client'
import { keys, useMeds } from '../../api/queries'
import type { Med, MedsDay } from '../../api/types'
import { Badge } from '../../components/Badge'
import { EmptyState } from '../../components/EmptyState'
import { ErrorState } from '../../components/ErrorState'
import { Skeleton } from '../../components/Skeleton'
import { useToast } from '../../components/Toast'
import { formatDate, useLang, useT, type Key, type Lang } from '../../i18n'
import { errorKey } from '../lock/errorKey'
import { useLock } from '../lock/useLock'
import './meds.css'

type Dose = MedsDay['today'][number] & { name?: string; strength?: string | null }
type Period = 'morning' | 'noon' | 'night'

const PERIODS: { id: Period; label: Key; icon: LucideIcon }[] = [
  { id: 'morning', label: 'meds.morning', icon: Sunrise },
  { id: 'noon', label: 'meds.noon', icon: Sun },
  { id: 'night', label: 'meds.night', icon: Moon },
]
const REFILL_AT = 7

/** Local calendar date, YYYY-MM-DD (not UTC: 7 a.m. in Manila is still "today"). */
function localDate(d = new Date()): string {
  const p = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`
}

/** Slots are "HH:MM" times from the schedule (or a named period). Before 11 is morning, before 16 noon. */
function periodOf(slot: string): Period {
  if (slot === 'morning' || slot === 'noon' || slot === 'night') return slot
  const h = Number(slot.split(':')[0])
  if (!Number.isFinite(h)) return 'morning'
  return h < 11 ? 'morning' : h < 16 ? 'noon' : 'night'
}

/** The backend sends `schedule` as JSON text (a raw DB column), while the plan says string[]: accept both. */
function scheduleOf(m: Med): string[] {
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

function slotTime(slot: string, lang: Lang): string {
  const m = slot.match(/^(\d{1,2}):(\d{2})$/)
  if (!m) return slot
  return formatDate(new Date(2000, 0, 1, Number(m[1]), Number(m[2])), lang, { hour: 'numeric', minute: '2-digit' })
}

function RefillBadge({ med }: { med: Med | undefined }) {
  const t = useT()
  if (med?.supply_left == null || med.supply_left > REFILL_AT) return null
  return <Badge tone="warn" icon={PackageOpen}>{t('meds.refillSoon', { n: med.supply_left })}</Badge>
}

function DoseRow({ dose, med, onToggle }: { dose: Dose; med: Med | undefined; onToggle: (d: Dose) => void }) {
  const t = useT()
  const [lang] = useLang()
  const taken = dose.taken_at != null
  const name = dose.name ?? med?.name ?? ''
  const strength = dose.strength ?? med?.strength
  const id = `dose-${dose.med_id}-${dose.slot.replace(/\W/g, '')}`
  return (
    <li className={['dose', taken && 'dose--taken'].filter(Boolean).join(' ')} data-testid="dose">
      <div className="dose__info" id={id}>
        <p className="dose__name">{name}{strength && <span className="dose__strength"> {strength}</span>}</p>
        <p className="dose__meta">
          <span className="tabular">{slotTime(dose.slot, lang)}</span>
          {taken && dose.taken_at && <span> · {t('meds.takenAt', { time: formatDate(dose.taken_at, lang, { hour: 'numeric', minute: '2-digit' }) })}</span>}
        </p>
        <RefillBadge med={med} />
      </div>
      <button type="button" className="dose__check" aria-pressed={taken} aria-describedby={id} onClick={() => onToggle(dose)}>
        <span className="dose__box" aria-hidden="true">{taken && <Check strokeWidth={3} />}</span>
        <span>{t(taken ? 'meds.taken' : 'meds.markTaken')}</span>
      </button>
    </li>
  )
}

function MedsSkeleton() {
  return (
    <div className="meds__skeleton" aria-busy="true">
      <Skeleton width="40%" height={28} />
      {[0, 1, 2].map(i => <Skeleton key={i} height={88} radius={20} />)}
    </div>
  )
}

export function MedsPage() {
  const t = useT()
  const [lang] = useLang()
  const toast = useToast()
  const qc = useQueryClient()
  const { profileId } = useLock()
  const date = useMemo(() => localDate(), [])
  const meds = useMeds(profileId, date)
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
      const name = dose.name ?? meds.data?.meds.find(m => m.id === dose.med_id)?.name ?? ''
      toast(take ? t('toasts.medTaken', { name }) : t('meds.untaken', { name }))
    },
    onError: (err, _v, ctx) => {
      if (ctx?.before) qc.setQueryData(key, ctx.before)
      toast(t(errorKey(err, 'toasts.failed')), 'error')
    },
    onSettled: () => qc.invalidateQueries({ queryKey: key }),
  })

  const byId = useMemo(() => new Map((meds.data?.meds ?? []).map(m => [m.id, m])), [meds.data])
  const groups = useMemo(() => {
    const g: Record<Period, Dose[]> = { morning: [], noon: [], night: [] }
    for (const d of (meds.data?.today ?? []) as Dose[]) g[periodOf(d.slot)].push(d)
    return g
  }, [meds.data])

  const onToggle = (dose: Dose) => toggle.mutate({ dose, take: dose.taken_at == null })

  return (
    <div className="page meds">
      <h1>{t('meds.title')}</h1>
      {meds.isPending ? <MedsSkeleton />
        : meds.isError ? <ErrorState message={errorKey(meds.error)} onRetry={() => { meds.refetch() }} />
        : meds.data.meds.length === 0 ? <EmptyState icon={Pill} title={t('meds.emptyTitle')} body={t('meds.emptyBody')} />
        : (
          <>
            <section className="meds__section" aria-labelledby="meds-today">
              <h2 id="meds-today" className="meds__h2">{t('meds.todayHeading')}</h2>
              {PERIODS.filter(p => groups[p.id].length > 0).map(({ id, label, icon: Icon }) => (
                <section key={id} className="meds__period" aria-labelledby={`period-${id}`}>
                  <h3 id={`period-${id}`} className="meds__h3"><Icon aria-hidden="true" strokeWidth={2} /><span>{t(label)}</span></h3>
                  <ul className="meds__list">
                    {groups[id].map(d => <DoseRow key={`${d.med_id}-${d.slot}`} dose={d} med={byId.get(d.med_id)} onToggle={onToggle} />)}
                  </ul>
                </section>
              ))}
            </section>

            <section className="meds__section" aria-labelledby="meds-all">
              <h2 id="meds-all" className="meds__h2">{t('meds.allMeds')}</h2>
              <ul className="meds__list">
                {meds.data.meds.map(m => (
                  <li key={m.id} className="medcard">
                    <p className="dose__name">{m.name}{m.strength && <span className="dose__strength"> {m.strength}</span>}</p>
                    {m.purpose && <p><span className="medcard__k">{t('meds.purpose')}:</span> {m.purpose}</p>}
                    {m.prescriber && (
                      <p className="medcard__line"><Stethoscope aria-hidden="true" strokeWidth={2} />
                        <span><span className="medcard__k">{t('meds.prescriber')}:</span> {m.prescriber}</span></p>
                    )}
                    {scheduleOf(m).length > 0 && <p className="tabular">{t('meds.times', { times: scheduleOf(m).map(x => slotTime(x, lang)).join(', ') })}</p>}
                    <RefillBadge med={m} />
                  </li>
                ))}
              </ul>
            </section>
          </>
        )}
    </div>
  )
}
