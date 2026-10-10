import { Link, useLocation, useNavigate } from 'react-router'
import { ArrowLeft } from 'lucide-react'
import { useT } from '../i18n'

/** Round back button: returns to the previous screen, or to `fallback` when the screen was opened directly. */
export function BackLink({ fallback = '/home' }: { fallback?: string }) {
  const t = useT()
  const navigate = useNavigate()
  const canGoBack = useLocation().key !== 'default' // react-router's first entry has the key 'default'
  return (
    <Link to={fallback} className="back-link" title={t('common.back')}
      onClick={e => { if (canGoBack) { e.preventDefault(); navigate(-1) } }}>
      <ArrowLeft aria-hidden="true" />
      <span className="sr-only">{t('common.back')}</span>
    </Link>
  )
}
