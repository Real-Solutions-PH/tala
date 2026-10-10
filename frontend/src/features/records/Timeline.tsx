import { Link } from 'react-router'
import { FileText, FlaskConical, Stethoscope, Syringe, type LucideIcon } from 'lucide-react'
import { useProfiles, useTimeline } from '../../api/queries'
import type { TimelineItem, TimelineKind } from '../../api/types'
import { ErrorState } from '../../components/ErrorState'
import { Skeleton } from '../../components/Skeleton'
import { formatDate, useLang, useT, type Key } from '../../i18n'
import { useLock } from '../lock/useLock'
import './records.css'

const KIND: Record<TimelineKind, { icon: LucideIcon; label: Key }> = {
  lab: { icon: FlaskConical, label: 'records.filterLab' },
  vaccine: { icon: Syringe, label: 'records.filterVaccine' },
  visit: { icon: Stethoscope, label: 'records.filterVisit' },
  document: { icon: FileText, label: 'records.filterDocument' },
}

/** A timeline row, as in the prototype: a tinted file-type tile, the title, then tags (type, person, date). */
function Row({ item, who }: { item: TimelineItem; who: string }) {
  const t = useT()
  const [lang] = useLang()
  const { icon: Icon, label } = KIND[item.kind]
  const body = (
    <>
      <span className={`tl-row__icon tl-row__icon--${item.kind}`} aria-hidden="true"><Icon strokeWidth={2} /></span>
      <span className="tl-row__text">
        <b className="tl-row__title">{item.title}</b>
        <span className="tags2">
          <span>{t(label)}</span>
          {who && <span>{who}</span>}
          <span><FileText aria-hidden="true" /><time dateTime={item.date}>{formatDate(item.date, lang)}</time></span>
        </span>
      </span>
    </>
  )
  // Lab results and documents are stored documents, so they open the viewer; visits and vaccines have no page.
  return item.kind === 'lab' || item.kind === 'document'
    ? <Link to={`/records/documents/${item.ref_id}`} className="tl-row tl-row--link">{body}</Link>
    : <div className="tl-row">{body}</div>
}

/** History of visits, results, vaccines and documents, newest first. */
export function Timeline() {
  const t = useT()
  const { profileId } = useLock()
  const q = useTimeline(profileId)
  const me = useProfiles().data?.find(p => p.id === profileId)
  const who = me ? (me.nickname ?? me.full_name) : ''

  return (
    <section className="sec timeline" aria-labelledby="timeline-title">
      <h2 id="timeline-title">{t('records.timelineTitle')}</h2>
      {q.isPending
        ? <ul className="panel tl" aria-busy="true">{[0, 1, 2].map(i => (
            <li key={i} className="tl-row">
              <Skeleton width={44} height={44} radius={12} />
              <span className="tl-row__text tl-row__text--skeleton"><Skeleton width="70%" height={18} /><Skeleton width="45%" height={14} /></span>
            </li>
          ))}</ul>
        : q.isError
          ? <ErrorState onRetry={() => { q.refetch() }} />
          : q.data.length === 0
            ? <p className="muted timeline__empty">{t('records.emptyBody')}</p>
            : <ul className="panel tl">{q.data.map(i => <li key={`${i.kind}-${i.ref_id}`}><Row item={i} who={who} /></li>)}</ul>}
    </section>
  )
}
