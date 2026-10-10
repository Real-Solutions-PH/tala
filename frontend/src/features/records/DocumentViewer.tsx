import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useLocation, useParams, useSearchParams } from 'react-router'
import { ArrowLeft, BookOpenText, FileWarning, ZoomIn, ZoomOut } from 'lucide-react'
import Markdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { ApiError } from '../../api/client'
import { Button } from '../../components/Button'
import { Card } from '../../components/Card'
import { ErrorState } from '../../components/ErrorState'
import { Skeleton } from '../../components/Skeleton'
import { formatDate, useLang, useT } from '../../i18n'
import { useDocument, type DocumentDetail } from './api'
import { findHighlight, type Quote } from './highlight'
import { ReviewExtraction } from './ReviewExtraction'
import './records.css'

const ZOOMS = [1, 1.5, 2, 3]

/** The backend's page URLs; built from `pages` only if an older server leaves them out. */
const pageUrls = (d: DocumentDetail) => d.page_urls?.length
  ? d.page_urls
  : Array.from({ length: Math.max(1, d.pages) }, (_, i) => `/api/documents/${d.id}/page/${i + 1}.png`)

// Minimal hast shapes, enough for the plugin below.
type HText = { type: 'text'; value: string; position?: { start: { offset?: number }; end: { offset?: number } } }
type HElement = { type: 'element'; tagName: string; properties: Record<string, unknown>; children: HNode[] }
type HNode = HText | HElement | { type: string; children?: HNode[] }

/**
 * Rehype plugin: wraps the source range [start, end) in <mark>. It uses each text node's position in the
 * markdown source and only touches nodes whose text is a verbatim slice of the source, so a range that
 * falls inside markdown syntax is simply left unmarked.
 */
function markRange(source: string, start: number, end: number) {
  const split = (node: HNode): HNode[] => {
    if (node.type !== 'text') {
      if ('children' in node && node.children) node.children = node.children.flatMap(split)
      return [node]
    }
    const n = node as HText
    const s = n.position?.start.offset
    const e = n.position?.end.offset
    if (s == null || e == null || e <= start || s >= end || source.slice(s, e) !== n.value) return [n]
    const a = Math.max(start, s) - s
    const b = Math.min(end, e) - s
    const out: HNode[] = []
    if (a > 0) out.push({ type: 'text', value: n.value.slice(0, a) })
    out.push({ type: 'element', tagName: 'mark', properties: { className: ['cite-mark'] }, children: [{ type: 'text', value: n.value.slice(a, b) }] })
    if (b < n.value.length) out.push({ type: 'text', value: n.value.slice(b) })
    return out
  }
  return () => (tree: HNode) => { split(tree) }
}

/** `layout` changes when something above the text resizes (a page image loading), so the mark is re-centred. */
function Transcript({ md, highlight, layout }: { md: string; highlight: { start: number; end: number } | null; layout: number }) {
  const t = useT()
  const ref = useRef<HTMLDivElement>(null)
  const plugins = useMemo(() => (highlight ? [markRange(md, highlight.start, highlight.end)] : []), [md, highlight])
  useEffect(() => {
    ref.current?.querySelector('mark')?.scrollIntoView({ block: 'center' })
  }, [plugins, layout])
  return (
    <div ref={ref} className="transcript" id="transcript">
      {highlight && <p className="transcript__cited small">{t('records.cited')}</p>}
      <Markdown remarkPlugins={[remarkGfm]} rehypePlugins={plugins}>{md}</Markdown>
    </div>
  )
}

/** A stored document: its page images (zoomable), what Kapiling read from it, and values to confirm. */
export function DocumentViewer() {
  const t = useT()
  const [lang] = useLang()
  const id = Number(useParams().id)
  const [params] = useSearchParams()
  const location = useLocation()
  const q = useDocument(id)
  const [zoom, setZoom] = useState(0)
  const [showText, setShowText] = useState<boolean | null>(null)
  const [loaded, setLoaded] = useState(0)

  // A citation opens this page as ?chunk=<id>, carrying its before/match/after quote in the router state.
  const chunk = Number(params.get('chunk'))
  const source = (location.state as { source?: Quote & { chunk_id?: number } } | null)?.source
  const quote = chunk && source && (source.chunk_id == null || source.chunk_id === chunk) ? source : null
  const doc = q.data
  const highlight = useMemo(() => findHighlight(doc?.transcript_md, quote), [doc?.transcript_md, quote])
  const textOpen = showText ?? !!highlight

  const reading = doc?.status === 'queued' || doc?.status === 'reading'
  const proposed = (doc?.observations ?? []).filter(o => o.status === 'proposed')
  const meta = [doc?.facility, doc?.date ? formatDate(doc.date, lang) : null].filter(Boolean).join(' · ')

  return (
    <div className="page document">
      <Link to="/records" className="btn btn--ghost back-link"><ArrowLeft aria-hidden="true" strokeWidth={2} /><span>{t('records.title')}</span></Link>
      <h1 className="document__title">{doc?.title ?? t('records.documents')}</h1>
      {meta && <p className="muted">{meta}</p>}

      {q.isPending ? <Skeleton height={360} radius={20} />
        : q.isError ? <ErrorState onRetry={() => { q.refetch() }} message={q.error instanceof ApiError && q.error.status === 404 ? 'errors.notFound' : 'errors.generic'} />
          : reading ? (
            <Card className="doc-status" role="status">
              <span className="spinner" aria-hidden="true" />
              <div>
                <p className="doc-status__title">{t('records.stillReading')}</p>
                <p className="muted">{t('records.stillReadingBody')}</p>
              </div>
            </Card>
          ) : doc!.status === 'failed' ? (
            <Card className="doc-status doc-status--failed" role="alert">
              <FileWarning aria-hidden="true" strokeWidth={2} />
              <div>
                <p className="doc-status__title">{t('records.readFailed')}</p>
                <p className="muted">{t('records.readFailedBody')}</p>
              </div>
            </Card>
          ) : (
            <>
              <ReviewExtraction key={doc!.id} documentId={doc!.id} proposed={proposed} />

              <div className="doc-zoom">
                <Button variant="secondary" icon={ZoomOut} disabled={zoom === 0} onClick={() => setZoom(z => Math.max(0, z - 1))}>{t('records.zoomOut')}</Button>
                <span className="doc-zoom__level num" aria-live="polite">{Math.round(ZOOMS[zoom] * 100)}%</span>
                <Button variant="secondary" icon={ZoomIn} disabled={zoom === ZOOMS.length - 1} onClick={() => setZoom(z => Math.min(ZOOMS.length - 1, z + 1))}>{t('records.zoomIn')}</Button>
              </div>
              {pageUrls(doc!).map((src, i) => ({ src, n: i + 1 })).map(({ src, n }) => (
                <figure key={src} className="doc-page">
                  <div className="doc-page__scroll" tabIndex={0}>
                    <img src={src} alt={t('records.pageAlt', { title: doc!.title, n })}
                      style={{ width: `${ZOOMS[zoom] * 100}%` }} onLoad={() => setLoaded(n => n + 1)} />
                  </div>
                  {pageUrls(doc!).length > 1 && <figcaption className="small muted">{t('records.pageOf', { n, total: pageUrls(doc!).length })}</figcaption>}
                </figure>
              ))}

              <Button variant={textOpen ? 'secondary' : 'primary'} size="lg" block icon={BookOpenText}
                aria-expanded={textOpen} aria-controls="transcript" onClick={() => setShowText(!textOpen)}>
                {textOpen ? t('records.hideText') : t('records.readText')}
              </Button>
              {textOpen && (doc!.transcript_md
                ? <Transcript md={doc!.transcript_md} highlight={highlight} layout={loaded} />
                : <p className="muted">{t('records.noTranscript')}</p>)}
            </>
          )}
    </div>
  )
}
