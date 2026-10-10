// "Who opened my records": the owner-only access log (spec section 3), newest first.
import { ScrollText } from 'lucide-react'
import { ApiError } from '../../api/client'
import { EmptyState } from '../../components/EmptyState'
import { ErrorState } from '../../components/ErrorState'
import { Skeleton } from '../../components/Skeleton'
import { formatDate, useLang, useT, type Key } from '../../i18n'
import { useAccessLog, type AccessLogRow } from './api'

const ACTIONS = new Set(['unlock', 'unlock_failed', 'view_summary', 'view_cards', 'view_access_log', 'add_representative',
  'remove_representative', 'change_pin', 'change_pin_failed', 'enrol_biometric', 'enrol_biometric_failed',
  'remove_biometric', 'change_emergency_fields', 'denied'])

/** The server stores UTC as 'YYYY-MM-DD HH:MM:SS'. */
const when = (at: string) => new Date(at.includes('T') ? at : `${at.replace(' ', 'T')}Z`)

export function AccessLog({ profileId, enabled = true }: { profileId: number | null; enabled?: boolean }) {
  const t = useT()
  const [lang] = useLang()
  const log = useAccessLog(profileId, enabled)

  if (log.isPending) return <div className="skeleton-stack" aria-busy="true"><Skeleton height={56} /><Skeleton height={56} /><Skeleton height={56} /></div>
  if (log.isError) {
    const owner = log.error instanceof ApiError && log.error.status === 403
    return <ErrorState message={owner ? 'settings.ownerOnly' : 'errors.generic'} onRetry={() => { log.refetch() }} />
  }
  if (log.data.length === 0) return <EmptyState icon={ScrollText} title={t('settings.accessLogEmpty')} body={t('settings.accessLogHint')} />

  const what = (r: AccessLogRow) => {
    const label = t((ACTIONS.has(r.action) ? `settings.log.${r.action}` : 'settings.log.other') as Key)
    return r.target === 'biometric' ? `${label}, ${t('settings.viaBiometric')}` : label
  }

  return (
    <ul className="log-list">
      {log.data.map((r, i) => (
        <li key={`${r.at}-${i}`}>
          <span className="log-list__who">{r.actor === 'unknown' ? t('settings.someone') : r.actor}</span>
          <span className="log-list__what">{what(r)}</span>
          <time className="log-list__when" dateTime={when(r.at).toISOString()}>
            {formatDate(when(r.at), lang, { dateStyle: 'medium', timeStyle: 'short' })}
          </time>
        </li>
      ))}
    </ul>
  )
}
