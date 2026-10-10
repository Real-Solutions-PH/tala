import { Link, useLocation } from 'react-router'
import type { Source } from '../../../api/types'
import { useT } from '../../../i18n'

/** Numbered citation chips; each opens the document at the cited chunk with the quote to highlight. */
export function Sources({ sources }: { sources: Source[] }) {
  const t = useT()
  const { pathname } = useLocation()
  if (!sources.length) return null
  return (
    <nav className="sources" aria-label={t('chat.sources')}>
      <p className="sources__label">{t('chat.sources')}</p>
      <ul>
        {sources.map(s => (
          <li key={`${s.n}-${s.chunk_id}`}>
            <Link className="source-chip" to={`/records/documents/${s.document_id}?chunk=${s.chunk_id}`}
              state={{ from: pathname, source: { chunk_id: s.chunk_id, before: s.before, match: s.match, after: s.after } }}>
              <span className="source-chip__n" aria-hidden="true">{s.n}</span>
              <span className="source-chip__title"><span className="sr-only">{s.n}. </span>{s.title}{s.page != null ? ` · p. ${s.page}` : ''}</span>
            </Link>
          </li>
        ))}
      </ul>
    </nav>
  )
}
