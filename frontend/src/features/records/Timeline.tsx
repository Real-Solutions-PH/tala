import { useState } from 'react'
import { Link } from 'react-router'
import { CalendarCheck, ChevronDown, ChevronRight, FileText, FlaskConical, Syringe, type LucideIcon } from 'lucide-react'
import { useTimeline } from '../../api/queries'
import type { TimelineItem, TimelineKind } from '../../api/types'
import { ErrorState } from '../../components/ErrorState'
import { Skeleton } from '../../components/Skeleton'
import { formatDate, useLang, useT, type Key } from '../../i18n'
import { useLock } from '../lock/useLock'
import './records.css'

const FILTERS: { kind?: TimelineKind; label: Key }[] = [
  { label: 'records.all' },
  { kind: 'lab', label: 'records.filterLab' },
  { kind: 'vaccine', label: 'records.filterVaccine' },
  { kind: 'visit', label: 'records.filterVisit' },
  { kind: 'document', label: 'records.filterDocument' },
]

const KIND: Record<TimelineKind, { icon: LucideIcon; label: Key }> = {
  lab: { icon: FlaskConical, label: 'records.filterLab' },
  vaccine: { icon: Syringe, label: 'records.filterVaccine' },
  visit: { icon: CalendarCheck, label: 'records.filterVisit' },
  document: { icon: FileText, label: 'records.filterDocument' },
}

function Row({ item }: { item: TimelineItem }) {
  const t = useT()
  const [lang] = useLang()
  const { icon: Icon, label } = KIND[item.kind]
  const body = (
    <>
      <span className={`tl-row__icon tl-row__icon--${item.kind}`} aria-hidden="true"><Icon strokeWidth={2} /></span>
      <span className="tl-row__text">
        <span className="tl-row__title">{item.title}</span>
        <span className="small muted">{t(label)} · <time dateTime={item.date}>{formatDate(item.date, lang)}</time></span>
      </span>
    </>
  )
  // Lab results and documents are stored documents, so they open the viewer; visits and vaccines have no page.
  return item.kind === 'lab' || item.kind === 'document'
    ? <Link to={`/records/documents/${item.ref_id}`} className="tl-row tl-row--link">{body}<ChevronRight className="tl-row__go" aria-hidden="true" /></Link>
    : <div className="tl-row">{body}</div>
}

/** History of visits, results, vaccines and documents, newest first, with filter chips. */
export function Timeline() {
  const t = useT()
  const { profileId } = useLock()
  const [kind, setKind] = useState<TimelineKind | undefined>()
  const q = useTimeline(profileId, kind)

  return (
    <section className="timeline" aria-labelledby="timeline-title">
      <h2 id="timeline-title">{t('records.timeline')}</h2>
      {/* One pill dropdown instead of five chips: a native select, so it is accessible and large to tap. */}
      <label className="tl-filter">
        <span className="sr-only">{t('records.filterLabel')}</span>
        <select value={kind ?? ''} onChange={e => setKind((e.target.value || undefined) as TimelineKind | undefined)}>
          {FILTERS.map(f => <option key={f.label} value={f.kind ?? ''}>{t(f.label)}</option>)}
        </select>
        <ChevronDown aria-hidden="true" />
      </label>
      {q.isPending
        ? <ul className="tl-list" aria-busy="true">{[0, 1, 2].map(i => (
            // Placeholder rows shaped like the real ones: an icon circle and two lines of text.
            <li key={i} className="tl-row">
              <Skeleton width={48} height={48} radius="50%" />
              <span className="tl-row__text tl-row__text--skeleton"><Skeleton width="70%" height={18} /><Skeleton width="45%" height={14} /></span>
            </li>
          ))}</ul>
        : q.isError
          ? <ErrorState onRetry={() => { q.refetch() }} />
          : q.data.length === 0
            ? <p className="muted timeline__empty">{kind ? t('records.filteredEmpty') : t('records.emptyBody')}</p>
            : <ul className="tl-list">{q.data.map(i => <li key={`${i.kind}-${i.ref_id}`}><Row item={i} /></li>)}</ul>}
    </section>
  )
}
