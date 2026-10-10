import { Link } from 'react-router'
import { FileText } from 'lucide-react'
import { formatDate, useLang, useT } from '../../../i18n'
import type { Of } from './types'

export function DocumentBlock({ block }: { block: Of<'document'> }) {
  const t = useT()
  const [lang] = useLang()
  return (
    <section className="cblock cblock--doc">
      <img className="cblock__thumb" src={block.thumb_url} alt="" />
      <div className="cblock__doc-body">
        <p className="cblock__strong">{block.title}</p>
        {block.date && <p className="cblock__muted">{formatDate(block.date, lang)}</p>}
        <Link className="btn btn--secondary" to={`/records/documents/${block.document_id}`}>
          <FileText aria-hidden="true" strokeWidth={2} /><span>{t('blocks.openDocument')}</span>
        </Link>
      </div>
    </section>
  )
}
